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
        config.rules_to_disable = ["IR-keyword-case", "IR-column-layout"]
        exit_code = run_linter(config)
        self.assertEqual(exit_code, 0) # Ignored, so exit 0
        
        # 2. Disable only for sql
        config = Config()
        config.paths = [path]
        config.rules_to_disable = ["sql:IR-keyword-case", "IR-column-layout"]
        exit_code = run_linter(config)
        self.assertEqual(exit_code, 0) # Ignored for sql, exit 0
        
        # 3. Disable for another language (e.g. java), which shouldn't affect sql
        config = Config()
        config.paths = [path]
        config.rules_to_disable = ["java:IR-keyword-case", "IR-column-layout"]
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
            "IR-keyword-case": False,
            "IR-column-layout": False
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
            "IR-keyword-case": {"enabled": False},
            "IR-column-layout": False
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
            "sql:IR-keyword-case": {"enabled": False},
            "IR-column-layout": False
        }
        exit_code = run_linter(config)
        self.assertEqual(exit_code, 0) # Ignored for sql, exit 0
        
        # Enable globally, but override for sql to false via boolean override
        config = Config()
        config.paths = [path]
        config.rule_configs = {
            "IR-keyword-case": {"enabled": True},
            "sql:IR-keyword-case": False,
            "IR-column-layout": False
        }
        exit_code = run_linter(config)
        self.assertEqual(exit_code, 0) # Ignored for sql, exit 0

    def test_column_layout_config_fallback(self):
        path = self.write_temp_file("test.sql", "SELECT col1, col2, col3 FROM users;")
        
        config = Config()
        config.paths = [path]
        exit_code = run_linter(config)
        self.assertEqual(exit_code, 0)
        
        config = Config()
        config.paths = [path]
        config.rule_configs = {
            "sql:IR-line-length": {"max_length": 20}
        }
        exit_code = run_linter(config)
        self.assertEqual(exit_code, 1)
        
        config.fix = True
        run_linter(config)
        with open(path, "r") as f:
            content = f.read()
            self.assertIn("col1,\n", content)
            
        # 3. If we explicitly override IR-column-layout's max_length to 100 (while line-length max_length remains 20),
        # column layout should use its explicit 100 limit, determine it fits on one line, and NOT wrap it.
        path2 = self.write_temp_file("test2.sql", "SELECT col1, col2, col3 FROM users;")
        config2 = Config()
        config2.paths = [path2]
        config2.rule_configs = {
            "sql:IR-line-length": {"max_length": 20},
            "sql:IR-column-layout": {"max_length": 100}
        }
        config2.fix = True
        run_linter(config2)
        with open(path2, "r") as f:
            content2 = f.read()
            self.assertEqual(content2, "SELECT col1, col2, col3 FROM users;")

    def test_base_indent_linting(self):
        # 1. Test IndentRule with a base indent of 8 spaces
        query = "        SELECT id, name\n        FROM users;"
        path_indent = self.write_temp_file("test_indent.sql", query)
        config_indent = Config()
        config_indent.paths = [path_indent]
        config_indent.rule_configs = {
            "sql:IR-indent": {"base_indent": 8}
        }
        exit_code = run_linter(config_indent)
        self.assertEqual(exit_code, 0)
        
        config_indent2 = Config()
        config_indent2.paths = [path_indent]
        config_indent2.rule_configs = {
            "sql:IR-indent": {"base_indent": 6}
        }
        exit_code = run_linter(config_indent2)
        self.assertEqual(exit_code, 1)

        # 2. Test LineLengthRule with a base indent of 20 spaces
        long_query = "                    SELECT id, name FROM users;"
        path_len = self.write_temp_file("test_len.sql", long_query)
        config_len = Config()
        config_len.paths = [path_len]
        config_len.rule_configs = {
            "sql:IR-indent": {"base_indent": 20},
            "sql:IR-line-length": {"max_length": 30}
        }
        exit_code = run_linter(config_len)
        self.assertEqual(exit_code, 0)

        # 3. Test ColumnLayoutRule with base indent of 20 spaces
        col_query = "                        SELECT col1, col2, col3\n                        FROM users;"
        path_col = self.write_temp_file("test_col.sql", col_query)
        config_col = Config()
        config_col.paths = [path_col]
        config_col.rule_configs = {
            "sql:IR-indent": {"base_indent": 20},
            "sql:IR-column-layout": {"max_length": 30}
        }
        exit_code = run_linter(config_col)
        self.assertEqual(exit_code, 0)

    def test_clause_alignment(self):
        query = "SELECT id, name\n  FROM users\nWHERE active = true;"
        path = self.write_temp_file("test_align.sql", query)
        
        config = Config()
        config.paths = [path]
        exit_code = run_linter(config)
        self.assertEqual(exit_code, 1)
        
        config.fix = True
        run_linter(config)
        with open(path, "r") as f:
            content = f.read()
            self.assertEqual(content, "SELECT id, name\nFROM users\nWHERE active = true;")
            
        # Test case where FROM is on the same line as SELECT in a multi-line query (should be wrapped to new line)
        query2 = "SELECT id, name FROM users\nWHERE active = true;"
        path2 = self.write_temp_file("test_align2.sql", query2)
        config2 = Config()
        config2.paths = [path2]
        exit_code = run_linter(config2)
        self.assertEqual(exit_code, 1)
        
        config2.fix = True
        run_linter(config2)
        with open(path2, "r") as f:
            content2 = f.read()
            self.assertEqual(content2, "SELECT id, name\nFROM users\nWHERE active = true;")

    def test_raw_content_string_checking(self):
        config = Config()
        config.content = "SELECT id FROM users;"
        config.lang = "sql"
        exit_code = run_linter(config)
        self.assertEqual(exit_code, 0)
        
        config = Config()
        config.content = "select id from users;"
        config.lang = "sql"
        exit_code = run_linter(config)
        self.assertEqual(exit_code, 1)
        
        config = Config()
        config.content = "SELECT id FROM users;"
        exit_code = run_linter(config)
        self.assertEqual(exit_code, 1)

    def test_stdin_piping_checking(self):
        from unittest.mock import patch
        
        with patch("sys.stdin.isatty", return_value=False), \
             patch("select.select", return_value=([sys.stdin], [], [])), \
             patch("sys.stdin.read", return_value="select id from users;"):
             
            config = Config()
            config.lang = "sql"
            exit_code = run_linter(config)
            self.assertEqual(exit_code, 1)
            
            config_fix = Config()
            config_fix.lang = "sql"
            config_fix.fix = True
            
            import io
            captured_stdout = io.StringIO()
            with patch("sys.stdout", captured_stdout):
                exit_code_fix = run_linter(config_fix)
                
            self.assertEqual(exit_code_fix, 0)
            self.assertEqual(captured_stdout.getvalue(), "SELECT id FROM users;")

    def test_disable_all_and_enable(self):
        query = "select id from users;"
        path = self.write_temp_file("test_disable.sql", query)
        
        config1 = Config()
        config1.paths = [path]
        self.assertEqual(run_linter(config1), 1)
        
        config2 = Config()
        config2.paths = [path]
        config2.disable_all = True
        self.assertEqual(run_linter(config2), 0)
        
        config3 = Config()
        config3.paths = [path]
        config3.disable_all = True
        config3.rules_to_enable = ["IR-keyword-case"]
        self.assertEqual(run_linter(config3), 1)
        
        config4 = Config()
        config4.paths = [path]
        config4.disable_all = True
        config4.rules_to_enable = ["IR-keyword-case"]
        config4.fix = True
        run_linter(config4)
        with open(path, "r") as f:
            content = f.read()
            self.assertEqual(content, "SELECT id FROM users;")

    def test_configurable_blank_lines(self):
        query = "SELECT * FROM users;\n\n\n\nSELECT * FROM roles;"
        path = self.write_temp_file("test_blank_lines.sql", query)
        
        # Default max_blank_lines = 1 (violates)
        config1 = Config()
        config1.paths = [path]
        config1.disable_all = True
        config1.rules_to_enable = ["IR-blank-lines"]
        config1.rule_configs = {"IR-blank-lines": {"max_blank_lines": 1}}
        self.assertEqual(run_linter(config1), 1)
        
        # Configured max_blank_lines = 3 (passes, as we have 3 consecutive blank lines)
        config2 = Config()
        config2.paths = [path]
        config2.disable_all = True
        config2.rules_to_enable = ["IR-blank-lines"]
        config2.rule_configs = {"IR-blank-lines": {"max_blank_lines": 3}}
        self.assertEqual(run_linter(config2), 0)

    def test_configurable_keyword_case(self):
        query = "SELECT * FROM users WHERE active = true AND foo = 1;"
        path = self.write_temp_file("test_keyword_case.sql", query)
        
        # Default: "foo" is not a keyword (passes)
        config1 = Config()
        config1.paths = [path]
        config1.disable_all = True
        config1.rules_to_enable = ["IR-keyword-case"]
        self.assertEqual(run_linter(config1), 0)
        
        # Configured: "foo" is added to additional_keywords (violates and gets fixed)
        config2 = Config()
        config2.paths = [path]
        config2.disable_all = True
        config2.rules_to_enable = ["IR-keyword-case"]
        config2.rule_configs = {"IR-keyword-case": {"additional_keywords": ["foo"]}}
        self.assertEqual(run_linter(config2), 1)
        
        config3 = Config()
        config3.paths = [path]
        config3.fix = True
        config3.disable_all = True
        config3.rules_to_enable = ["IR-keyword-case"]
        config3.rule_configs = {"IR-keyword-case": {"additional_keywords": ["foo"]}}
        run_linter(config3)
        with open(path, "r") as f:
            content = f.read()
            self.assertEqual(content, "SELECT * FROM users WHERE active = true AND FOO = 1;")

if __name__ == "__main__":
    unittest.main()
