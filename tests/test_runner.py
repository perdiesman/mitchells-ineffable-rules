import os
import sys
import unittest
import tempfile
from unittest.mock import patch

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
        path = self.write_temp_file("test.sql", "select id from t;")
        config = Config()
        config.paths = [path]
        config.fix = True
        
        exit_code = run_linter(config)
        self.assertEqual(exit_code, 0) # Fixed successfully
        
        with open(path, "r") as f:
            self.assertEqual(f.read(), "SELECT id FROM t;")

    def test_language_specific_disable(self):
        # A file with select (which violates keyword case)
        path = self.write_temp_file("test.sql", "select id from t;")
        
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
        path = self.write_temp_file("test.sql", "SELECT id FROM t;")
        
        # 1. Global max_length is 120 (default), line length is 17. No violations.
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
        path = self.write_temp_file("test.sql", "select id from t;")
        
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
        path = self.write_temp_file("test.sql", "select id from t;")
        
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
        path = self.write_temp_file("test.sql", "select id from t;")
        
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
            "sql:IR-column-layout": {"max_length": 100},
            "sql:IR-expression-split": {"max_line_length": 100},
            "sql:IR-clause-alignment": {"max_length": 100}
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
        config.rules_to_disable = ["IR-boolean-comparison"]
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
        config2.rules_to_disable = ["IR-boolean-comparison"]
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

    def test_dynamic_base_indent(self):
        # Indented by 8 spaces
        query = "        SELECT id, name\n        FROM users;"
        path = self.write_temp_file("test_base_indent.sql", query)
        
        # Test 1: Indent rule with no configured base_indent (should auto-detect 8 spaces, so it passes)
        config1 = Config()
        config1.paths = [path]
        config1.disable_all = True
        config1.rules_to_enable = ["IR-indent"]
        self.assertEqual(run_linter(config1), 0)
        
        # Test 2: Line length rule with no configured base_indent (should auto-detect 8 spaces, so it passes)
        config2 = Config()
        config2.paths = [path]
        config2.disable_all = True
        config2.rules_to_enable = ["IR-line-length"]
        # Limit set to 20. Raw line 1 has 23 chars. Effective has 15 chars. (passes)
        config2.rule_configs = {"IR-line-length": {"max_length": 20}}
        self.assertEqual(run_linter(config2), 0)

    def test_configurable_function_case(self):
        # "foo" is parsed as a function call because it is followed by '('
        query = "SELECT foo(id) FROM users;"
        path = self.write_temp_file("test_function_case.sql", query)
        
        # Default: "foo" is not excluded, so it violates function case default lowercase (but is lowercase, wait, let's use uppercase "FOO(id)" so it violates)
        query = "SELECT FOO(id) FROM users;"
        with open(path, "w") as f:
            f.write(query)
            
        config1 = Config()
        config1.paths = [path]
        config1.disable_all = True
        config1.rules_to_enable = ["IR-function-case"]
        self.assertEqual(run_linter(config1), 1) # Violates (FOO must be lowercase foo)
        
        # Configured: add "foo" to additional_exclusions (passes)
        config2 = Config()
        config2.paths = [path]
        config2.disable_all = True
        config2.rules_to_enable = ["IR-function-case"]
        config2.rule_configs = {"IR-function-case": {"additional_exclusions": ["foo"]}}
        self.assertEqual(run_linter(config2), 0)

    def test_quiet_warnings_runner(self):
        query = "select id from users;"  # Violates IR-keyword-case
        path = self.write_temp_file("test_quiet_warnings.sql", query)

        # 1. Test quiet option (no stdout/stderr but sets exit code)
        config_quiet = Config()
        config_quiet.paths = [path]
        config_quiet.disable_all = True
        config_quiet.rules_to_enable = ["IR-keyword-case"]
        config_quiet.quiet = True

        import io
        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()
        with patch("sys.stdout", captured_stdout), patch("sys.stderr", captured_stderr):
            exit_code = run_linter(config_quiet)

        self.assertEqual(exit_code, 1)
        self.assertEqual(captured_stdout.getvalue(), "")
        self.assertEqual(captured_stderr.getvalue(), "")

        # 2. Test warnings-only and no-warnings options
        # We need a rule with severity warning. Let's configure IR-keyword-case to severity warning
        config_warn_only = Config()
        config_warn_only.paths = [path]
        config_warn_only.disable_all = True
        config_warn_only.rules_to_enable = ["IR-keyword-case"]
        config_warn_only.rule_configs = {"IR-keyword-case": {"severity": "warning"}}
        config_warn_only.warnings_only = True

        captured_stdout = io.StringIO()
        with patch("sys.stdout", captured_stdout):
            exit_code = run_linter(config_warn_only)
        # Should report violation and exit 0 (since warning severity doesn't fail the lint run)
        self.assertEqual(exit_code, 0)
        self.assertIn("[WARN] IR-keyword-case", captured_stdout.getvalue())

        # Test no-warnings option (should hide the warning)
        config_no_warn = Config()
        config_no_warn.paths = [path]
        config_no_warn.disable_all = True
        config_no_warn.rules_to_enable = ["IR-keyword-case"]
        config_no_warn.rule_configs = {"IR-keyword-case": {"severity": "warning"}}
        config_no_warn.no_warnings = True

        captured_stdout = io.StringIO()
        with patch("sys.stdout", captured_stdout):
            exit_code = run_linter(config_no_warn)
        # Should hide the warning completely
        self.assertEqual(exit_code, 0)
        self.assertEqual(captured_stdout.getvalue(), "")

    def test_xml_linting(self):
        # 1. Malformed XML fails
        malformed = "<root>\n  <child>\n</root>"
        path = self.write_temp_file("test.xml", malformed)
        
        config = Config()
        config.paths = [path]
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-well-formed"]
        self.assertEqual(run_linter(config), 1)

        # 2. Fix single quotes to double quotes in XML attributes
        single_quoted = "<root attr='val' />"
        with open(path, "w") as f:
            f.write(single_quoted)

        config_fix = Config()
        config_fix.paths = [path]
        config_fix.disable_all = True
        config_fix.rules_to_enable = ["IR-xml-attribute-quotes"]
        config_fix.fix = True
        self.assertEqual(run_linter(config_fix), 0)

        with open(path, "r") as f:
            self.assertEqual(f.read(), '<root attr="val" />')

        # 3. XML indentation check and fix
        bad_indent = "<root>\n  <child />\n</root>"
        with open(path, "w") as f:
            f.write(bad_indent)

        config_indent = Config()
        config_indent.paths = [path]
        config_indent.disable_all = True
        config_indent.rules_to_enable = ["IR-xml-indent"]
        config_indent.fix = True
        self.assertEqual(run_linter(config_indent), 0)

        with open(path, "r") as f:
            self.assertEqual(f.read(), "<root>\n    <child />\n</root>")

        # 3b. XML indentation with nested SQL tags (e.g. <if>) aligning to SQL indentation
        sql_nested_tags = (
            '<mapper namespace="MyMapper">\n'
            '    <select id="query">\n'
            '        SELECT id\n'
            '        FROM users\n'
            '        WHERE id IN (\n'
            '            SELECT user_id\n'
            '            FROM roles\n'
            '          <if test="admin">\n'
            '                WHERE role_name = \'admin\'\n'
            '        </if>\n'
            '        )\n'
            '    </select>\n'
            '</mapper>'
        )
        with open(path, "w") as f:
            f.write(sql_nested_tags)

        config_indent2 = Config()
        config_indent2.paths = [path]
        config_indent2.disable_all = True
        config_indent2.rules_to_enable = ["IR-xml-indent"]
        config_indent2.fix = True
        self.assertEqual(run_linter(config_indent2), 0)

        with open(path, "r") as f:
            expected = (
                '<mapper namespace="MyMapper">\n'
                '    <select id="query">\n'
                '        SELECT id\n'
                '        FROM users\n'
                '        WHERE id IN (\n'
                '            SELECT user_id\n'
                '            FROM roles\n'
                '            <if test="admin">WHERE role_name = \'admin\'</if>\n'
                '        )\n'
                '    </select>\n'
                '</mapper>'
            )
            self.assertEqual(f.read(), expected)

        # 3c. XML indentation with nested SQL tags in <sql> fragment aligning to SQL indentation
        sql_fragment_nested_tags = (
            '<mapper namespace="MyMapper">\n'
            '    <sql id="fragment">\n'
            '        SELECT id\n'
            '        FROM users\n'
            '        WHERE active = 1\n'
            '      <if test="admin">\n'
            '            AND role = \'admin\'\n'
            '    </if>\n'
            '    </sql>\n'
            '</mapper>'
        )
        with open(path, "w") as f:
            f.write(sql_fragment_nested_tags)

        config_indent3 = Config()
        config_indent3.paths = [path]
        config_indent3.disable_all = True
        config_indent3.rules_to_enable = ["IR-xml-indent"]
        config_indent3.fix = True
        self.assertEqual(run_linter(config_indent3), 0)

        with open(path, "r") as f:
            expected = (
                '<mapper namespace="MyMapper">\n'
                '    <sql id="fragment">\n'
                '        SELECT id\n'
                '        FROM users\n'
                '        WHERE active = 1\n'
                '        <if test="admin">AND role = \'admin\'</if>\n'
                '    </sql>\n'
                '</mapper>'
            )
            self.assertEqual(f.read(), expected)

        # 4. XML line length check
        long_line = "<root>\n    <child />\n" + ("A" * 121) + "\n</root>"
        with open(path, "w") as f:
            f.write(long_line)

        config_len = Config()
        config_len.paths = [path]
        config_len.disable_all = True
        config_len.rules_to_enable = ["IR-xml-line-length"]
        self.assertEqual(run_linter(config_len), 1)

        # 5. XML MyBatis embedded SQL check and fix
        mybatis_xml = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">\n<mapper namespace="my_namespace.MyMapper">\n    <select id="selectListByQuery">\n        select my_column from my_schema.my_table t\n    </select>\n</mapper>'
        with open(path, "w") as f:
            f.write(mybatis_xml)

        config_mybatis = Config()
        config_mybatis.paths = [path]
        config_mybatis.disable_all = True
        config_mybatis.rules_to_enable = ["IR-xml-mybatis-sql", "IR-keyword-case"]
        config_mybatis.fix = True
        self.assertEqual(run_linter(config_mybatis), 0)

        with open(path, "r") as f:
            expected = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">\n<mapper namespace="my_namespace.MyMapper">\n    <select id="selectListByQuery">\n        SELECT my_column FROM my_schema.my_table t\n    </select>\n</mapper>'
            self.assertEqual(f.read(), expected)

    def test_xml_mybatis_sql_severity(self):
        # A select query violating IR-in-exists: select id from t where id in (select id from t2)
        xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<mapper namespace="MyMapper">\n    <select id="query">\n        SELECT id FROM t WHERE id IN (SELECT id FROM t2)\n    </select>\n</mapper>'
        path = self.write_temp_file("test_severity.xml", xml_content)

        # 1. Without warning override (should fail with exit code 1)
        config_error = Config()
        config_error.paths = [path]
        config_error.disable_all = True
        config_error.rules_to_enable = ["IR-xml-mybatis-sql", "IR-in-exists"]
        # Make sure SQL rules are configured to error
        config_error.rule_configs = {
            "IR-in-exists": {"severity": "error"}
        }
        
        exit_code = run_linter(config_error)
        self.assertEqual(exit_code, 1)

        # 2. With warning override for IR-in-exists (should pass with exit code 0)
        config_warn = Config()
        config_warn.paths = [path]
        config_warn.disable_all = True
        config_warn.rules_to_enable = ["IR-xml-mybatis-sql", "IR-in-exists"]
        config_warn.rule_configs = {
            "IR-in-exists": {"severity": "warning"}
        }

        import io
        captured_stdout = io.StringIO()
        with patch("sys.stdout", captured_stdout):
            exit_code = run_linter(config_warn)
            
        self.assertEqual(exit_code, 0)
        self.assertIn("[WARN] IR-in-exists", captured_stdout.getvalue())

    def test_xml_mybatis_sql_entities(self):
        # A select query with &gt; entity inside the XML content
        xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<mapper namespace="MyMapper">\n    <select id="query">\n        SELECT id FROM t WHERE id &gt; 10\n    </select>\n</mapper>'
        path = self.write_temp_file("test_entities.xml", xml_content)

        config = Config()
        config.paths = [path]
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-mybatis-sql", "IR-alias-as"]
        config.fix = True

        exit_code = run_linter(config)
        self.assertEqual(exit_code, 0)

        # The XML file must remain intact and not have "AS" inserted inside "&gt;"
        with open(path, "r") as f:
            content = f.read()
            self.assertIn("id &gt; 10", content)
            self.assertNotIn("&AS gt;", content)

    def test_xml_mybatis_sql_line_mapping(self):
        # XML file with a self-comparison on line 5
        xml_content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n' # 1
            '<mapper namespace="MyMapper">\n'          # 2
            '    <update id="query">\n'                # 3
            '        SELECT id FROM t\n'               # 4
            '        WHERE id = id;\n'                 # 5
            '    </update>\n'                          # 6
            '</mapper>'                                # 7
        )
        path = self.write_temp_file("test_mapping.xml", xml_content)

        config = Config()
        config.paths = [path]
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-mybatis-sql", "IR-self-comparison"]

        import io
        captured_stdout = io.StringIO()
        with patch("sys.stdout", captured_stdout):
            exit_code = run_linter(config)

        self.assertEqual(exit_code, 1)
        self.assertIn("test_mapping.xml:5", captured_stdout.getvalue())

    def test_xml_mybatis_sql_indentation(self):
        # XML file with a query having incorrect clause indentation relative to base indent (8 spaces)
        xml_content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<mapper namespace="MyMapper">\n'
            '    <select id="query">\n'
            '        SELECT id\n'
            '      FROM t;\n'
            '    </select>\n'
            '</mapper>'
        )
        path = self.write_temp_file("test_mybatis_indent.xml", xml_content)

        config = Config()
        config.paths = [path]
        config.disable_all = True
        # Enable IR-xml-mybatis-sql, IR-indent, and IR-clause-alignment
        config.rules_to_enable = ["IR-xml-mybatis-sql", "IR-indent", "IR-clause-alignment"]
        config.fix = True

        exit_code = run_linter(config)
        self.assertEqual(exit_code, 0)

        # The FROM clause should be aligned to exactly 8 spaces (matching SELECT's base indentation)
        with open(path, "r") as f:
            content = f.read()
            expected = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<mapper namespace="MyMapper">\n'
                '    <select id="query">\n'
                '        SELECT id\n'
                '        FROM t;\n'
                '    </select>\n'
                '</mapper>'
            )
            self.assertEqual(content, expected)

    def test_line_ranges_filtering(self):
        # A file with multiple violations on different lines
        # Line 1: SELECT * (has wildcard check error)
        # Line 2: FROM users
        # Line 3: WHERE active = true (correct)
        # Line 4: and age > 18 (keyword lowercase error)
        sql_content = "SELECT *\nFROM users\nWHERE active = true\nand age > 18;"
        path = self.write_temp_file("test_lines.sql", sql_content)

        # 1. Check with lines config restricting to line 4 only
        config = Config()
        config.paths = [path]
        config.disable_all = True
        config.rules_to_enable = ["IR-select-wildcard", "IR-keyword-case"]
        config.lines = {4}
        config.fix = True

        exit_code = run_linter(config)
        self.assertEqual(exit_code, 0)

        # Only line 4 should be fixed to 'AND age > 18;'. Line 1 SELECT * must NOT be fixed/altered.
        with open(path, "r") as f:
            content = f.read()
            expected = "SELECT *\nFROM users\nWHERE active = true\nAND age > 18;"
            self.assertEqual(content, expected)

    def test_block_range_lines_filtering(self):
        # A file with two MyBatis select blocks:
        # Block 1 spans lines 3-7:
        # Line 3: <select id="query1">
        # Line 4:     SELECT id
        # Line 5:     FROM users
        # Line 6:     where active = true (keyword case error)
        # Line 7: </select>
        #
        # Block 2 spans lines 8-12:
        # Line 8: <select id="query2">
        # Line 9:     SELECT name
        # Line 10:    FROM roles
        # Line 11:    where role_name = 'admin' (keyword case error)
        # Line 12: </select>
        xml_content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<mapper namespace="MyMapper">\n'
            '    <select id="query1">\n'
            '        SELECT id\n'
            '        FROM users\n'
            '        where active = true\n'
            '    </select>\n'
            '    <select id="query2">\n'
            '        SELECT name\n'
            '        FROM roles\n'
            '        where role_name = \'admin\'\n'
            '    </select>\n'
            '</mapper>'
        )
        path = self.write_temp_file("test_mybatis_blocks.xml", xml_content)

        # We only pass line 5 (which is inside block 1, but doesn't have the violation).
        # Because line 5 is in block 1, block 1's lines are expanded.
        # So line 6 should get fixed! But block 2 has no line in lines, so line 11 should NOT get fixed.
        config = Config()
        config.paths = [path]
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-mybatis-sql", "IR-keyword-case"]
        config.lines = {5}
        config.fix = True

        exit_code = run_linter(config)
        self.assertEqual(exit_code, 0)

        with open(path, "r") as f:
            content = f.read()
            expected = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<mapper namespace="MyMapper">\n'
                '    <select id="query1">\n'
                '        SELECT id\n'
                '        FROM users\n'
                '        WHERE active = true\n'
                '    </select>\n'
                '    <select id="query2">\n'
                '        SELECT name\n'
                '        FROM roles\n'
                '        where role_name = \'admin\'\n'
                '    </select>\n'
                '</mapper>'
            )
            self.assertEqual(content, expected)

    def test_xml_line_length_attribute_wrapping(self):
        # A root tag with long attributes exceeding 120 limit
        xml_content = '<root firstAttribute="some_very_long_value_to_exceed_one_hundred_and_twenty_characters_limit_to_trigger_wrapping" secondAttribute="another_value_to_wrap" />'
        path = self.write_temp_file("test_wrap.xml", xml_content)

        config = Config()
        config.paths = [path]
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-line-length"]
        config.fix = True

        exit_code = run_linter(config)
        self.assertEqual(exit_code, 0)

        # The wrapped attributes should be indented exactly 2 levels (8 spaces) relative to the tag opening line (which is at 0 spaces)
        with open(path, "r") as f:
            content = f.read()
            expected = (
                '<root firstAttribute="some_very_long_value_to_exceed_one_hundred_and_twenty_characters_limit_to_trigger_wrapping"\n'
                '        secondAttribute="another_value_to_wrap" />'
            )
            self.assertEqual(content, expected)

    def test_xml_tag_collapse(self):
        # A choose-when block with multi-line tags that can fit under 120 chars
        xml_content = (
            '<mapper namespace="MyMapper">\n'
            '    <choose>\n'
            '        <when test="admin">\n'
            '            role = \'admin\'\n'
            '        </when>\n'
            '        <otherwise>\n'
            '            role = \'user\'\n'
            '        </otherwise>\n'
            '    </choose>\n'
            '</mapper>'
        )
        path = self.write_temp_file("test_collapse.xml", xml_content)

        config = Config()
        config.paths = [path]
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-indent"]
        config.fix = True

        exit_code = run_linter(config)
        self.assertEqual(exit_code, 0)

        with open(path, "r") as f:
            content = f.read()
            expected = (
                '<mapper namespace="MyMapper">\n'
                '    <choose>\n'
                '        <when test="admin">role = \'admin\'</when>\n'
                '        <otherwise>role = \'user\'</otherwise>\n'
                '    </choose>\n'
                '</mapper>'
            )
            self.assertEqual(content, expected)

    def test_sql_function_call_wrap(self):
        # A long SQL function call exceeding 120 characters should be wrapped
        sql_content = (
            "SELECT id,\n"
            "    schema_name.some_very_long_custom_function_name(#{paramName}::TIMESTAMP WITH TIME ZONE - INTERVAL '15 minute') alias_name\n"
            "FROM users"
        )
        path = self.write_temp_file("test_func_wrap.sql", sql_content)

        config = Config()
        config.paths = [path]
        config.disable_all = True
        config.rules_to_enable = ["IR-line-length"]
        config.fix = True

        exit_code = run_linter(config)
        self.assertEqual(exit_code, 0)

        with open(path, "r") as f:
            content = f.read()
            expected = (
                "SELECT id,\n"
                "    schema_name.some_very_long_custom_function_name(\n"
                "        #{paramName}::TIMESTAMP WITH TIME ZONE - INTERVAL '15 minute'\n"
                "    ) alias_name\n"
                "FROM users"
            )
            self.assertEqual(content, expected)

if __name__ == "__main__":
    unittest.main()
