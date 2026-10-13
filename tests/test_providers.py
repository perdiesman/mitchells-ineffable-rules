import tempfile
import textwrap
import unittest
from pathlib import Path

from mir.engine.config import Config
from mir.engine.provider_interface import BaseProvider, ProviderCapabilities
from mir.engine.providers_loader import ProviderValidationError, load_providers, validate_provider_class
from mir.engine.runner import find_files
from mir.engine.disabler import get_disabled_rules_map, get_file_language


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
            self.assertEqual(find_files([directory]), sorted([str(python_file), str(typescript_file)]))

    def test_provider_directives_and_language_detection(self):
        source = (
            "# IR-start-ruff:F401\n"
            "import os\n"
            "# IR-end-ruff:F401\n"
        )
        disabled = get_disabled_rules_map(source, "sample.py")
        self.assertIn(2, disabled["IR-ruff:F401"])
        self.assertEqual(get_file_language("sample.ts"), "typescript")


if __name__ == "__main__":
    unittest.main()
