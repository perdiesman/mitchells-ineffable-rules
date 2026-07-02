import os
import sys
import unittest
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mir.engine.config import Config
from mir.engine.runner import run_linter

class TestRunnerIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        
    def tearDown(self):
        self.temp_dir.cleanup()
        
    def write_temp_file(self, filename: str, content: str) -> str:
        filepath = os.path.join(self.temp_dir.name, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    def test_runner_check_mode(self):
        path = self.write_temp_file("test.sql", "select * from t;")
        config = Config()
        config.paths = [path]
        config.fix = False
        config.dry_run = False
        
        exit_code = run_linter(config)
        self.assertEqual(exit_code, 1) # Has violations
        
    def test_runner_fix_mode(self):
        path = self.write_temp_file("test.sql", "select * from t;")
        config = Config()
        config.paths = [path]
        config.fix = True
        
        exit_code = run_linter(config)
        self.assertEqual(exit_code, 0) # Fixed successfully
        
        with open(path, "r") as f:
            self.assertEqual(f.read(), "SELECT * FROM t;")

    def test_language_specific_disable(self):
        # A file with select (which violates keyword case)
        path = self.write_temp_file("test.sql", "select * from t;")
        
        # 1. Disable globally
        config = Config()
        config.paths = [path]
        config.rules_to_disable = ["IR-keyword-case"]
        exit_code = run_linter(config)
        self.assertEqual(exit_code, 0) # Ignored, so exit 0
        
        # 2. Disable only for sql
        config = Config()
        config.paths = [path]
        config.rules_to_disable = ["sql:IR-keyword-case"]
        exit_code = run_linter(config)
        self.assertEqual(exit_code, 0) # Ignored for sql, exit 0
        
        # 3. Disable for another language (e.g. java), which shouldn't affect sql
        config = Config()
        config.paths = [path]
        config.rules_to_disable = ["java:IR-keyword-case"]
        exit_code = run_linter(config)
        self.assertEqual(exit_code, 1) # Not ignored for sql, exit 1

    def test_language_specific_config_override(self):
        # Write a file with 15 characters on line 1
        path = self.write_temp_file("test.sql", "SELECT * FROM t;")
        
        # 1. Global max_length is 120 (default), line length is 16. No violations.
        config = Config()
        config.paths = [path]
        exit_code = run_linter(config)
        self.assertEqual(exit_code, 0)
        
        # 2. Set global max_length to 10. Violates line-length.
        config = Config()
        config.paths = [path]
        config.rule_configs = {
            "IR-line-length": {"max_length": 10}
        }
        exit_code = run_linter(config)
        self.assertEqual(exit_code, 1)
        
        # 3. Set global max_length to 10, but override SQL max_length to 20. Should pass.
        config = Config()
        config.paths = [path]
        config.rule_configs = {
            "IR-line-length": {"max_length": 10},
            "sql:IR-line-length": {"max_length": 20}
        }
        exit_code = run_linter(config)
        self.assertEqual(exit_code, 0)

    def test_rule_config_disablement_boolean(self):
        # Violates keyword case
        path = self.write_temp_file("test.sql", "select * from t;")
        
        # Disable via boolean config
        config = Config()
        config.paths = [path]
        config.rule_configs = {
            "IR-keyword-case": False
        }
        exit_code = run_linter(config)
        self.assertEqual(exit_code, 0) # Ignored, exit 0

    def test_rule_config_disablement_dict(self):
        # Violates keyword case
        path = self.write_temp_file("test.sql", "select * from t;")
        
        # Disable via enabled parameter in dict
        config = Config()
        config.paths = [path]
        config.rule_configs = {
            "IR-keyword-case": {"enabled": False}
        }
        exit_code = run_linter(config)
        self.assertEqual(exit_code, 0) # Ignored, exit 0

    def test_rule_config_disablement_lang_override(self):
        # Violates keyword case
        path = self.write_temp_file("test.sql", "select * from t;")
        
        # Enable globally, but override for sql to false
        config = Config()
        config.paths = [path]
        config.rule_configs = {
            "IR-keyword-case": {"enabled": True},
            "sql:IR-keyword-case": {"enabled": False}
        }
        exit_code = run_linter(config)
        self.assertEqual(exit_code, 0) # Ignored for sql, exit 0
        
        # Enable globally, but override for sql to false via boolean override
        config = Config()
        config.paths = [path]
        config.rule_configs = {
            "IR-keyword-case": {"enabled": True},
            "sql:IR-keyword-case": False
        }
        exit_code = run_linter(config)
        self.assertEqual(exit_code, 0) # Ignored for sql, exit 0

if __name__ == "__main__":
    unittest.main()
