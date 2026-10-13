import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mir.engine.config import load_config

class TestConfig(unittest.TestCase):
    def test_version_matches_package_metadata(self):
        output = StringIO()
        with self.assertRaises(SystemExit) as raised:
            with redirect_stdout(output):
                load_config(["--version"])
        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(output.getvalue().strip(), "mir-linter 0.2.0")

    def test_default_config(self):
        config = load_config([])
        self.assertFalse(config.fix)
        self.assertFalse(config.dry_run)
        self.assertFalse(config.verbose)
        self.assertEqual(config.paths, ["."])
        self.assertEqual(config.language_configs, {})

    def test_language_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".ir-config.yaml")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write("languages:\n  java:\n    generated:\n      mode: check\n")
            config = load_config(["--config", path])
            self.assertEqual(config.language_configs["java"]["generated"]["mode"], "check")

    def test_provider_configuration(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as stream:
            stream.write(
                "providers:\n"
                "  ruff:\n"
                "    enabled: true\n"
                "    unsafe_fixes: false\n"
                "provider_dirs: [tools/providers]\n"
                "disable_providers: [prettier]\n"
            )
            path = stream.name
        try:
            config = load_config(["--config", path, "--enable-provider", "eslint"])
            self.assertTrue(config.provider_configs["ruff"]["enabled"])
            self.assertEqual(config.provider_dirs, ["tools/providers"])
            self.assertEqual(config.providers_to_enable, ["eslint"])
            self.assertEqual(config.providers_to_disable, ["prettier"])
        finally:
            os.unlink(path)

    def test_cli_overrides(self):
        config = load_config(["--fix", "--verbose", "file1.sql", "file2.sql"])
        self.assertTrue(config.fix)
        self.assertFalse(config.dry_run)
        self.assertTrue(config.verbose)
        self.assertEqual(config.paths, ["file1.sql", "file2.sql"])

    def test_staged_uses_commit_profile_inputs(self):
        config = load_config(["--staged", "--fix", "--profile", "commit"])
        self.assertTrue(config.staged)
        self.assertTrue(config.fix)
        self.assertEqual(config.profile, "commit")

    def test_lines_reject_multiple_paths(self):
        with self.assertRaises(SystemExit):
            load_config(["--lines", "2-3", "first.sql", "second.sql"])

    def test_env_overrides(self):
        os.environ["IR_FIX"] = "True"
        os.environ["IR_VERBOSE"] = "1"
        os.environ["IR_DISABLE"] = "IR-line-length,IR-another"
        try:
            config = load_config([])
            self.assertTrue(config.fix)
            self.assertTrue(config.verbose)
            self.assertIn("IR-line-length", config.rules_to_disable)
            self.assertIn("IR-another", config.rules_to_disable)
        finally:
            del os.environ["IR_FIX"]
            del os.environ["IR_VERBOSE"]
            del os.environ["IR_DISABLE"]

    def test_quiet_warnings_flags(self):
        # Default flags should be False
        config = load_config([])
        self.assertFalse(config.quiet)
        self.assertFalse(config.warnings_only)
        self.assertFalse(config.no_warnings)

        # CLI overrides
        config2 = load_config(["--quiet", "--warnings-only", "--no-warnings"])
        self.assertTrue(config2.quiet)
        self.assertTrue(config2.warnings_only)
        self.assertTrue(config2.no_warnings)

        # Env overrides
        os.environ["IR_QUIET"] = "True"
        os.environ["IR_WARNINGS_ONLY"] = "yes"
        os.environ["IR_NO_WARNINGS"] = "1"
        try:
            config3 = load_config([])
            self.assertTrue(config3.quiet)
            self.assertTrue(config3.warnings_only)
            self.assertTrue(config3.no_warnings)
        finally:
            del os.environ["IR_QUIET"]
            del os.environ["IR_WARNINGS_ONLY"]
            del os.environ["IR_NO_WARNINGS"]

if __name__ == "__main__":
    unittest.main()
