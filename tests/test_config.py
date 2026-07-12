import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mir.engine.config import load_config

class TestConfig(unittest.TestCase):
    def test_default_config(self):
        config = load_config([])
        self.assertFalse(config.fix)
        self.assertFalse(config.dry_run)
        self.assertFalse(config.verbose)
        self.assertEqual(config.paths, ["."])

    def test_cli_overrides(self):
        config = load_config(["--fix", "--verbose", "file1.sql", "file2.sql"])
        self.assertTrue(config.fix)
        self.assertFalse(config.dry_run)
        self.assertTrue(config.verbose)
        self.assertEqual(config.paths, ["file1.sql", "file2.sql"])

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
