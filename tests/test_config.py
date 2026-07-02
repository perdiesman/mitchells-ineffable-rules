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

if __name__ == "__main__":
    unittest.main()
