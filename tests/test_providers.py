import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from mir.engine.config import Config
from mir.engine.disabler import get_disabled_rules_map, get_file_language
from mir.engine.provider_interface import (
    BaseProvider,
    ProviderCapabilities,
    ProviderContext,
    ProviderResult,
)
from mir.engine.providers_loader import (
    ProviderValidationError,
    load_providers,
    validate_provider_class,
)
from mir.engine.runner import find_files, process_document, run_linter
from mir.providers.eslint import EslintProvider
from mir.providers.node_bridge import project_root_for_executable
from mir.providers.prettier import PrettierProvider

RUFF = shutil.which("ruff") or str(Path(sys.executable).with_name("ruff"))
if not Path(RUFF).is_file():
    RUFF = None


class TestProviders(unittest.TestCase):
    def test_builtin_provider_languages_and_extensions(self):
        providers = {provider.provider_id: provider for provider in load_providers()}
        self.assertEqual(set(providers), {"ruff", "eslint", "prettier"})
        self.assertIn(".py", providers["ruff"].extensions)
        self.assertIn(".ts", providers["prettier"].extensions)

    def test_invalid_provider_is_rejected(self):
        class Invalid(BaseProvider):
            provider_id = "invalid"
            capabilities = ProviderCapabilities()

        with self.assertRaises(ProviderValidationError):
            validate_provider_class(Invalid)

    def test_local_provider_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "sample.py").write_text(
                textwrap.dedent(
                    """
                    from mir.engine.provider_interface import BaseProvider, ProviderResult

                    class SampleProvider(BaseProvider):
                        provider_id = "sample"
                        description = "Sample provider."
                        languages = ("sample",)
                        extensions = (".sample",)
                        def run(self, content, context, provider_config):
                            return ProviderResult(content)
                    """
                ),
                encoding="utf-8",
            )
            providers = load_providers([directory])
            self.assertIn("sample", {provider.provider_id for provider in providers})

    def test_provider_extensions_participate_in_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            python_file = Path(directory, "sample.py")
            typescript_file = Path(directory, "sample.ts")
            ignored_file = Path(directory, "sample.txt")
            for path in (python_file, typescript_file, ignored_file):
                path.write_text("value\n", encoding="utf-8")
            self.assertEqual(
                find_files([directory]),
                sorted([str(python_file), str(typescript_file)]),
            )

    def test_provider_directives_and_language_detection(self):
        source = "# IR-start-ruff:F401\nimport os\n# IR-end-ruff:F401\n"
        disabled = get_disabled_rules_map(source, "sample.py")
        self.assertIn(2, disabled["IR-ruff:F401"])
        self.assertEqual(get_file_language("sample.ts"), "typescript")

    def test_prettier_bridge_honors_exact_version(self):
        context = ProviderContext(
            "/tmp/sample.ts", "typescript", frozenset(), False, True, None, {}
        )
        response = {"content": "const value = 1;\n", "version": "3.6.2"}
        with (
            patch(
                "mir.providers.prettier.resolve_executable",
                return_value="/project/node_modules/.bin/prettier",
            ),
            patch(
                "mir.providers.prettier.node_request", return_value=response
            ) as request,
        ):
            result = PrettierProvider().run(
                "const value=1\n",
                context,
                {"required_version": "3.6.2", "timeout_seconds": 10},
            )
        self.assertEqual(result.content, response["content"])
        self.assertEqual(result.version, "3.6.2")
        self.assertEqual(request.call_args.args[2]["path"], "/tmp/sample.ts")

    def test_eslint_bridge_applies_reported_fix(self):
        context = ProviderContext(
            "/tmp/sample.ts", "typescript", frozenset(), False, True, None, {}
        )
        violation = {
            "messages": [
                {
                    "ruleId": "prefer-const",
                    "message": "Use const.",
                    "line": 1,
                    "column": 1,
                    "severity": 2,
                    "fix": {"range": [0, 3], "text": "const"},
                }
            ],
            "version": "9.35.0",
        }
        clean = {"messages": [], "version": "9.35.0"}
        with (
            patch(
                "mir.providers.eslint.resolve_executable",
                return_value="/project/node_modules/.bin/eslint",
            ),
            patch(
                "mir.providers.eslint.node_request",
                side_effect=[violation, clean, clean],
            ),
        ):
            result = EslintProvider().run(
                "let value = 1;\n",
                context,
                {"fix": True, "required_version": "9.35.0", "timeout_seconds": 10},
            )
        self.assertEqual(result.content, "const value = 1;\n")
        self.assertEqual(result.findings, [])

    def test_node_project_root_preserves_project_symlink(self):
        self.assertEqual(
            project_root_for_executable("/project/node_modules/.bin/eslint"),
            "/project",
        )

    def test_provider_pipeline_converges_across_ordered_tools(self):
        calls = {"eslint": 0, "prettier": 0}

        def eslint_run(provider, content, context, provider_config):
            calls["eslint"] += 1
            updated = content.replace("let value = 1;", "const value = 1;")
            return ProviderResult(updated, changed=updated != content)

        def prettier_run(provider, content, context, provider_config):
            calls["prettier"] += 1
            updated = content.replace("let value=1", "let value = 1;")
            return ProviderResult(updated, changed=updated != content)

        config = Config()
        config.fix = True
        with (
            patch.object(EslintProvider, "run", eslint_run),
            patch.object(PrettierProvider, "run", prettier_run),
        ):
            result = process_document(
                config, "let value=1\n", "/tmp/provider-pipeline.ts", "typescript"
            )
        self.assertEqual(result.content, "const value = 1;\n")
        self.assertGreaterEqual(calls["eslint"], 3)
        self.assertEqual(result.diagnostics, [])

    @unittest.skipUnless(RUFF, "Ruff optional dependency is not installed")
    def test_real_ruff_fix_is_clean_and_idempotent(self):
        config = Config()
        config.fix = True
        config.provider_configs = {"ruff": {"enabled": True, "executable": RUFF}}
        source = "import os\n\ndef add( left,right ):\n return left+right\n"
        first = process_document(config, source, "/tmp/generic_provider.py", "python")
        second = process_document(
            config, first.content, "/tmp/generic_provider.py", "python"
        )
        self.assertEqual(
            first.content, "def add(left, right):\n    return left + right\n"
        )
        self.assertEqual(first.violations, [])
        self.assertEqual(first.diagnostics, [])
        self.assertEqual(second.content, first.content)

    @unittest.skipUnless(RUFF, "Ruff optional dependency is not installed")
    def test_real_ruff_respects_force_excluded_stdin_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text(
                '[tool.ruff]\nexclude = ["generated"]\n', encoding="utf-8"
            )
            generated = root / "generated" / "sample.py"
            generated.parent.mkdir()
            source = "def add( left,right ):\n return left+right\n"
            generated.write_text(source, encoding="utf-8")
            config = Config()
            config.fix = True
            config.provider_configs = {"ruff": {"enabled": True, "executable": RUFF}}
            result = process_document(config, source, str(generated), "python")
            self.assertEqual(result.content, source)
            self.assertEqual(result.violations, [])
            self.assertEqual(result.diagnostics, [])

    @unittest.skipUnless(RUFF, "Ruff optional dependency is not installed")
    def test_staged_ruff_updates_index_and_preserves_unstaged_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(
                ["git", "config", "user.name", "MIR Test"], cwd=root, check=True
            )
            subprocess.run(
                ["git", "config", "user.email", "mir@example.invalid"],
                cwd=root,
                check=True,
            )
            path = root / "sample.py"
            path.write_text(
                "def add( left,right ):\n return left+right\n", encoding="utf-8"
            )
            subprocess.run(["git", "add", "sample.py"], cwd=root, check=True)
            path.write_text(
                "def add( left,right ):\n return left+right\n# unstaged note\n",
                encoding="utf-8",
            )
            config = Config()
            config.staged = True
            config.fix = True
            config.provider_configs = {"ruff": {"enabled": True, "executable": RUFF}}
            with patch("mir.engine.git_staged.repository_root", return_value=root):
                self.assertEqual(run_linter(config), 0)
            staged = subprocess.run(
                ["git", "show", ":sample.py"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            self.assertEqual(staged, "def add(left, right):\n    return left + right\n")
            self.assertTrue(
                path.read_text(encoding="utf-8").endswith("# unstaged note\n")
            )


if __name__ == "__main__":
    unittest.main()
