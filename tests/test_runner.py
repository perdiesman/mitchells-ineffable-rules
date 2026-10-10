import os
import sys
import unittest
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mir.engine.config import Config
from mir.engine.rule_interface import BaseRule, Violation
from mir.engine.runner import process_document, remap_selected_lines, run_linter
from mir.rules.xml.xml_mybatis_sql import (
    between_delimiter_source_edits,
    get_mybatis_protected_signatures,
    join_case_source_edits,
)

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

    def test_selected_lines_follow_inserted_formatter_output(self):
        original = "SELECT value\nFROM sample\nWHERE enabled = true\n"
        fixed = "SELECT value\nFROM\n    sample\nWHERE enabled = true\n"

        self.assertEqual(remap_selected_lines(original, fixed, {2, 3}), {2, 3, 4})

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

    def test_formatter_cycle_does_not_persist_a_partial_state(self):
        class OscillatingRule(BaseRule):
            rule_id = "IR-test-oscillation"
            is_fixable = "yes"

            def check(self, content, file_path, rule_config):
                return [
                    Violation(
                        self.rule_id,
                        1,
                        "Oscillating test fixture.",
                        [content],
                        is_fixable=True,
                    )
                ]

            def fix(self, content, file_path, rule_config):
                return "second\n" if content == "first\n" else "first\n"

        rule = OscillatingRule()
        violation = rule.check("first\n", "cycle.xml", {})[0]
        config = Config()
        config.fix = True

        with patch(
            "mir.engine.runner._collect",
            return_value=([(violation, rule, "error")], []),
        ):
            result = process_document(config, "first\n", "cycle.xml", "xml")

        self.assertEqual(result.content, "first\n")
        self.assertEqual(result.violations, [(violation, rule, "error")])
        self.assertTrue(
            any("formatting cycle" in item for item in result.diagnostics)
        )

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

    def test_xml_mybatis_commit_profile_preserves_protected_sql_syntax(self):
        xml_content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<mapper namespace="GenericMapper">\n'
            '    <select id="query">\n'
            '        select payload-&gt;&gt;\'key\' from sample_table\n'
            '        where created_at between #{start} and #{end}\n'
            '          and make_interval(days =&gt; #{limit}) &gt; interval \'1 day\'\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        result = process_document(config, xml_content, "generic.xml", "xml")

        self.assertEqual(
            get_mybatis_protected_signatures(result.content),
            get_mybatis_protected_signatures(xml_content),
        )
        self.assertIn("payload -&gt;&gt; 'key'", result.content)
        self.assertIn("between #{start} AND #{end}", result.content)
        self.assertIn("days =&gt; #{limit}", result.content)
        self.assertNotIn("#{END}", result.content)
        self.assertNotIn("#{LIMIT}", result.content)

    def test_xml_mybatis_repeated_dynamic_predicates_are_mapped_atomically(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="search">\n'
            '        select item_id from sample_item\n'
            '        where\n'
            '            <if test="start != null and end != null">\n'
            "                recorded_at between timezone('utc', '${start}') and timezone('utc', '${end}') and\n"
            '            </if>\n'
            '            <if test="start != null and end == null">\n'
            "                recorded_at &gt;= timezone('utc', '${start}') and\n"
            '            </if>\n'
            '            active = true\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.fix = True

        result = process_document(config, xml_content, "generic.xml", "xml")

        self.assertEqual(
            get_mybatis_protected_signatures(result.content),
            get_mybatis_protected_signatures(
                xml_content.replace("active = true", "active")
            ),
        )
        self.assertFalse(
            any("protected MyBatis SQL syntax changed" in item for item in result.diagnostics)
        )

    def test_xml_mybatis_repeated_static_select_lists_use_column_layout(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="first">\n'
            '        SELECT\n'
            '            first_identifier,\n'
            '            second_identifier,\n'
            '            third_identifier,\n'
            '            fourth_identifier,\n'
            '            fifth_identifier,\n'
            '            sixth_identifier,\n'
            '            seventh_identifier\n'
            '        FROM sample_items_for_period(\n'
            '                #{period}\n'
            '            ) AS sample_item\n'
            '    </select>\n'
            '    <select id="second">\n'
            '        SELECT\n'
            '        first_identifier,\n'
            '        second_identifier,\n'
            '        third_identifier,\n'
            '        fourth_identifier,\n'
            '        fifth_identifier,\n'
            '        sixth_identifier,\n'
            '        seventh_identifier\n'
            '        FROM sample_items_for_period(\n'
            '                #{period}\n'
            '            ) AS sample_item\n'
            '        <if test="activeOnly">\n'
            '            WHERE active = TRUE\n'
            '        </if>\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            '        first_identifier,\n'
            '        second_identifier,\n'
            '        third_identifier,\n'
            '        fourth_identifier,\n'
            '        fifth_identifier,\n'
            '        sixth_identifier,\n'
            '        seventh_identifier\n',
            '            first_identifier,\n'
            '            second_identifier,\n'
            '            third_identifier,\n'
            '            fourth_identifier,\n'
            '            fifth_identifier,\n'
            '            sixth_identifier,\n'
            '            seventh_identifier\n',
        ).replace(
            '        FROM sample_items_for_period(\n'
            '                #{period}\n'
            '            ) AS sample_item',
            '        FROM sample_items_for_period(\n'
            '            #{period}\n'
            '        ) sample_item',
        ).replace(
            '        <if test="activeOnly">\n'
            '            WHERE active = TRUE\n'
            '        </if>',
            '        <if test="activeOnly">WHERE active</if>',
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertEqual(
            get_mybatis_protected_signatures(first.content),
            get_mybatis_protected_signatures(expected),
        )

    def test_xml_mybatis_dynamic_joined_table_function_keeps_sql_indentation(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="joinedFunction">\n'
            '        <choose>\n'
            '            <when test="usePeriod">\n'
            '                SELECT item.id\n'
            '                FROM sample.item item\n'
            '                    JOIN sample.items_for_period(\n'
            "                        '${start}',\n"
            "                        '${end}'\n"
            '                    ) period_item ON period_item.id = item.id\n'
            '            </when>\n'
            '        </choose>\n'
            '    </sql>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            '                FROM sample.item item\n',
            '                FROM\n'
            '                    sample.item item\n',
        ).replace(
            '                    JOIN sample.items_for_period(\n'
            "                        '${start}',\n"
            "                        '${end}'\n"
            '                    ) period_item ON period_item.id = item.id',
            '                    JOIN sample.items_for_period(\n'
            "                            '${start}',\n"
            "                            '${end}'\n"
            '                        ) period_item ON period_item.id = item.id',
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertEqual(
            get_mybatis_protected_signatures(first.content),
            get_mybatis_protected_signatures(xml_content),
        )

    def test_xml_indent_preserves_dynamic_table_function_on_continuations(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM sample_item item\n'
            '        <if test="withPeriods">\n'
            '            LEFT JOIN sample_items_for_period(\n'
            '                    #{start},\n'
            '                    #{end}\n'
            '                ) period_item ON period_item.item_id = item.item_id\n'
            '                AND period_item.enabled\n'
            '        </if>\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-indent"]
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, xml_content)
        self.assertEqual(second.content, xml_content)
        self.assertFalse(first.violations)

    def test_xml_mybatis_dynamic_join_modifier_aligns_with_join(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="joinedFunction">\n'
            '        SELECT item_id\n'
            '        FROM\n'
            '            sample_item item\n'
            '            JOIN generate_series(\n'
            '                #{start},\n'
            '                #{end}\n'
            '            ) period_start ON true\n'
            '                <if test="optional">\n'
            '                    LEFT\n'
            '                </if>\n'
            '            JOIN sample_period period USING (period_start)\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            '                <if test="optional">\n'
            '                    LEFT\n'
            '                </if>',
            '            <if test="optional">LEFT</if>',
        )
        config = Config()
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-indent"]
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_expanded_dynamic_table_function_keeps_join_indent(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="periods">\n'
            '        <choose>\n'
            '            <when test="hourly">\n'
            '                SELECT period_start\n'
            "                FROM sample_item item JOIN generate_series('${start}', '${end}', '${hours} Hours'::interval) period_start ON item.recorded_at BETWEEN period_start AND period_start + '${hours} Hours'::interval\n"
            '            </when>\n'
            '        </choose>\n'
            '    </sql>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="periods">\n'
            '        <choose>\n'
            '            <when test="hourly">\n'
            '                SELECT period_start\n'
            '                FROM\n'
            '                    sample_item item\n'
            '                    JOIN generate_series(\n'
            "                            '${start}',\n"
            "                            '${end}',\n"
            "                            '${hours} Hours'::interval\n"
            '                        ) period_start ON item.recorded_at BETWEEN period_start AND period_start\n'
            "                        + '${hours} Hours'::interval\n"
            '            </when>\n'
            '        </choose>\n'
            '    </sql>\n'
            '</mapper>'
        )
        config = Config()
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_compacts_short_static_join_predicates(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="joinedItems">\n'
            '        SELECT item.item_id\n'
            '        FROM sample_item item\n'
            '            JOIN sample_owner owner ON owner.owner_id = item.owner_id\n'
            '                AND owner.active\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            'JOIN sample_owner owner ON owner.owner_id = item.owner_id\n'
            '                AND owner.active',
            'JOIN sample_owner owner ON owner.owner_id = item.owner_id AND owner.active',
        ).replace(
            '        FROM sample_item item\n',
            '        FROM\n'
            '            sample_item item\n',
        )
        config = Config()
        config.profile = "commit"
        config.fix = True
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-mybatis-sql", "IR-join-on-multi"]

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)

    def test_xml_indent_formats_generated_column_list_fragment(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="Base_Column_List">\n'
            '    sample_item.item_id AS sample_item_id, sample_item.item_name AS sample_item_name,\n'
            '    sample_item.owner_id AS sample_item_owner_id\n'
            '    </sql>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="Base_Column_List">\n'
            '        sample_item.item_id AS sample_item_id,\n'
            '        sample_item.item_name AS sample_item_name,\n'
            '        sample_item.owner_id AS sample_item_owner_id\n'
            '    </sql>\n'
            '</mapper>'
        )
        config = Config()
        config.fix = True
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-indent"]

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)

    def test_xml_mybatis_anchors_clauses_after_column_include(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="Base_Column_List">\n'
            '        sample_item.item_id AS sample_item_id,\n'
            '        sample_item.item_name AS sample_item_name\n'
            '    </sql>\n'
            '    <select id="items">\n'
            '        SELECT\n'
            '            <include refid="Base_Column_List" />\n'
            '    FROM sample_item\n'
            '    WHERE sample_item.enabled\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            '    FROM sample_item\n    WHERE sample_item.enabled',
            '        FROM sample_item\n        WHERE sample_item.enabled',
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)

    def test_xml_mybatis_reusable_dynamic_column_list_is_clean(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="Basic_Column_List">\n'
            '        <if test="distinct">DISTINCT</if>\n'
            '        sample_item.item_id AS sample_item_id,\n'
            '        sample_item.item_name AS sample_item_name\n'
            '    </sql>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, xml_content)
        self.assertEqual(second.content, xml_content)
        self.assertFalse(first.violations)
        self.assertFalse(second.violations)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_trim_owned_where_is_clean(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="Basic_Where">\n'
            '        <if test="included">\n'
            '            <trim prefix="WHERE" prefixOverrides="WHERE ">\n'
            '                <trim prefixOverrides="AND |OR ">\n'
            '                    <include refid="Example_Where_Clause" />\n'
            '                </trim>\n'
            '            </trim>\n'
            '        </if>\n'
            '    </sql>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, xml_content)
        self.assertEqual(second.content, xml_content)
        self.assertFalse(first.violations)
        self.assertFalse(second.violations)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_external_query_include_preserves_parentheses(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT included_item.* FROM (\n'
            '            <include refid="external.Mapper.Query" />\n'
            '        ) AS included_item\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertIn("(\n", first.content)
        self.assertIn(") included_item", first.content)
        self.assertEqual(second.content, first.content)
        self.assertFalse(
            any(item[0].rule_id == "IR-paren-single" for item in first.violations)
        )
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_foreach_join_expands_from_clause(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <insert id="items">\n'
            '        <foreach collection="items" item="item" separator=" UNION ">\n'
            '            SELECT source_item.item_id\n'
            '            FROM (SELECT #{item.id} AS item_id\n'
            '                FROM source_item_input\n'
            '            ) source_item\n'
            '                JOIN sample_item existing ON existing.item_id = source_item.item_id\n'
            '        </foreach>\n'
            '    </insert>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertIn("            FROM\n                (", first.content)
        self.assertIn("                (\n                    SELECT", first.content)
        self.assertEqual(second.content, first.content)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_insert_columns_preserve_dynamic_body_indent(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <insert id="items">\n'
            '        INSERT INTO sample_item (\n'
            '                item_id\n'
            '                <if test="named">,\n'
            '                item_name</if>\n'
            '            )\n'
            '        SELECT item_id, item_name FROM source_item\n'
            '    </insert>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <insert id="items">\n'
            '        INSERT INTO sample_item (\n'
            '            item_id\n'
            '            <if test="named">\n'
            '                    ,\n'
            '                    item_name\n'
            '            </if>\n'
            '        )\n'
            '        SELECT item_id, item_name FROM source_item\n'
            '    </insert>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_preserves_multiline_update_in_dynamic_block(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <update id="items">\n'
            '        <if test="included">\n'
            '            UPDATE sample_item SET item_name = #{itemName}\n'
            '            WHERE item_id = #{itemId};\n'
            '        </if>\n'
            '    </update>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, xml_content)
        self.assertEqual(second.content, xml_content)
        self.assertFalse(first.violations)
        self.assertFalse(first.diagnostics)

    def test_xml_indent_keeps_optional_where_include_at_clause_indent(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <update id="updateItems">\n'
            '        UPDATE sample_item\n'
            '        SET\n'
            '            item_name = #{itemName}\n'
            '            <if test="filter != null">\n'
            '                <include refid="Update_Where_Clause" />\n'
            '            </if>\n'
            '    </update>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            '            <if test="filter != null">\n'
            '                <include refid="Update_Where_Clause" />\n'
            '            </if>',
            '        <if test="filter != null">\n'
            '            <include refid="Update_Where_Clause" />\n'
            '        </if>',
        )
        config = Config()
        config.fix = True
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-indent"]

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)

    def test_xml_mybatis_generator_limits_blank_line_runs(self):
        xml_content = (
            '<generatorConfiguration>\n'
            '    <context id="generic">\n'
            '        <!-- generated tables -->\n'
            '\n'
            '\n'
            '        <table tableName="sample_item" />\n'
            '\n'
            '\n'
            '\n'
            '    </context>\n'
            '</generatorConfiguration>'
        )
        expected = (
            '<generatorConfiguration>\n'
            '    <context id="generic">\n'
            '        <!-- generated tables -->\n'
            '\n'
            '        <table tableName="sample_item" />\n'
            '\n'
            '    </context>\n'
            '</generatorConfiguration>'
        )
        config = Config()
        config.fix = True
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-mybatis-blank-lines"]

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)

    def test_xml_indent_expands_derived_table_include(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item.item_id\n'
            '        FROM\n'
            '            sample_item item\n'
            '            LEFT JOIN (<include refid="OwnerTotals" />            ) owner '\
            'ON owner.item_id = item.item_id\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            '            LEFT JOIN (<include refid="OwnerTotals" />            ) owner '\
            'ON owner.item_id = item.item_id',
            '            LEFT JOIN (\n'
            '                    <include refid="OwnerTotals" />\n'
            '                ) owner ON owner.item_id = item.item_id',
        )
        config = Config()
        config.fix = True
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-indent"]

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)

    def test_xml_mybatis_applies_host_semantics_around_include(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="OwnerTotals">\n'
            '        SELECT owner_id, count(*) AS item_count\n'
            '        FROM sample_item\n'
            '        GROUP BY owner_id\n'
            '    </sql>\n'
            '    <select id="items">\n'
            '        SELECT item.item_id\n'
            '        FROM\n'
            '            sample_item item\n'
            '            INNER JOIN (\n'
            '                    <include refid="OwnerTotals" />\n'
            '                ) owner ON owner.owner_id = item.owner_id\n'
            '        WHERE item.enabled = FALSE\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace("INNER JOIN", "JOIN").replace(
            "item.enabled = FALSE", "NOT item.enabled"
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)
        self.assertFalse(second.diagnostics)

    def test_xml_mybatis_uppercases_repeated_dynamic_fragment_keywords(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="Generated_Where_Clause">\n'
            '        <where>\n'
            '            <choose>\n'
            '                <when test="primary">and ${condition}</when>\n'
            '                <otherwise>and ${fallback}</otherwise>\n'
            '            </choose>\n'
            '        </where>\n'
            '    </sql>\n'
            '</mapper>'
        )
        expected = xml_content.replace(">and ", ">AND ")
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)
        self.assertFalse(second.diagnostics)

    def test_xml_mybatis_reports_included_fragment_only_at_its_definition(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="Item_Filter">where item.enabled</sql>\n'
            '    <select id="items">\n'
            '        SELECT item_id FROM sample_item\n'
            '        <include refid="Item_Filter" />\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-mybatis-sql", "IR-keyword-case"]

        result = process_document(config, xml_content, "generic.xml", "xml")
        keyword_findings = [
            violation
            for violation, _, _ in result.violations
            if violation.rule_id == "IR-keyword-case"
        ]

        self.assertEqual(len(keyword_findings), 1)
        self.assertEqual(keyword_findings[0].line_number, 2)

    def test_xml_mybatis_commit_profile_applies_declared_boolean_rewrites(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="booleanPredicates">\n'
            '        SELECT enabled = TRUE AS enabled_flag\n'
            '        FROM sample_item\n'
            '        WHERE coalesce(enabled, FALSE) = TRUE\n'
            '        <if test="includeHidden == true">\n'
            '            AND #{showHidden} = FALSE\n'
            '            AND recorded_at &gt;= #{start} AND recorded_at &lt;= #{end}\n'
            '        </if>\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            '        WHERE coalesce(enabled, FALSE) = TRUE\n',
            '        WHERE coalesce(enabled, FALSE)\n',
        ).replace(
            '            AND #{showHidden} = FALSE\n',
            '            AND NOT #{showHidden}\n',
        ).replace(
            'recorded_at &gt;= #{start} AND recorded_at &lt;= #{end}',
            'recorded_at BETWEEN #{start} AND #{end}',
        )
        config = Config()
        config.profile = "commit"
        config.fix = True
        config.disable_all = True
        config.rules_to_enable = [
            "IR-xml-mybatis-sql",
            "IR-boolean-comparison",
            "IR-between",
        ]

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertNotIn("unsafe embedded fix", "\n".join(first.diagnostics))
        self.assertIn("includeHidden == true", first.content)
        self.assertIn("SELECT enabled = TRUE AS enabled_flag", first.content)

    def test_xml_mybatis_commit_profile_removes_statement_boundary_blank_lines(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '\n'
            '        SELECT item_id\n'
            '\n'
            '\n'
            '        FROM sample_item\n'
            '\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '\n'
            '        FROM sample_item\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)

    def test_xml_mybatis_formats_text_beside_inline_tags(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="from">from sample_table</sql>\n'
            '    <select id="count">\n'
            '        SELECT COUNT(*) <include refid="from" />\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        result = process_document(config, xml_content, "generic.xml", "xml")

        self.assertIn('SELECT count(*) <include refid="from" />', result.content)
        self.assertNotIn("IR-function-case", [item[0].rule_id for item in result.violations])

    def test_xml_mybatis_include_consumers_do_not_edit_shared_fragment_sources(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="fromFragment">from sample_table where created_at::TIMESTAMPTZ &gt; #{start}</sql>\n'
            '    <select id="first">SELECT COUNT(*) <include refid="fromFragment" /></select>\n'
            '    <select id="second">SELECT COUNT(*) <include refid="fromFragment" /></select>\n'
            '</mapper>'
        )
        config = Config()
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(second.content, first.content)
        self.assertFalse(
            any("protected MyBatis SQL syntax changed" in item for item in first.diagnostics)
        )
        self.assertIn(
            "FROM sample_table WHERE created_at::TIMESTAMP WITH TIME ZONE &gt; #{start}",
            first.content,
        )
        self.assertEqual(first.content.count("SELECT count(*) <include"), 2)

    def test_xml_mybatis_included_cte_before_repeated_local_ctes_converges(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="sourceStage">SELECT item_id FROM sample_source</sql>\n'
            '    <insert id="first">\n'
            '        WITH staged AS (<include refid="sourceStage" />), mapped AS (\n'
            '            SELECT st.item_id, owner.owner_id\n'
            '            FROM staged st\n'
            '            JOIN sample_owner owner ON owner.item_id = st.item_id\n'
            '        )\n'
            '        INSERT INTO sample_target (item_id, owner_id)\n'
            '        SELECT item_id, owner_id FROM mapped\n'
            '    </insert>\n'
            '    <insert id="second">\n'
            '        WITH staged AS (<include refid="sourceStage" />), mapped AS (\n'
            '            SELECT st.item_id, owner.owner_id\n'
            '            FROM staged st\n'
            '            JOIN sample_owner owner ON owner.item_id = st.item_id\n'
            '        )\n'
            '        INSERT INTO sample_archive (item_id, owner_id)\n'
            '        SELECT item_id, owner_id FROM mapped\n'
            '    </insert>\n'
            '</mapper>\n'
        )
        config = Config()
        config.fix = True
        config.profile = "commit"

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertFalse(
            any("converge" in diagnostic for diagnostic in first.diagnostics)
        )
        self.assertEqual(second.content, first.content)
        self.assertEqual(first.content.count("            SELECT"), 2)
        self.assertEqual(first.content.count("            FROM\n"), 2)
        self.assertEqual(first.content.count("                staged st"), 2)

    def test_xml_mybatis_fragment_semantic_rewrite_updates_consumer_signatures(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="activeFragment">FROM sample_item WHERE enabled = TRUE</sql>\n'
            '    <select id="first">SELECT item_id <include refid="activeFragment" /></select>\n'
            '    <select id="second">SELECT count(*) <include refid="activeFragment" /></select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-mybatis-sql", "IR-boolean-comparison"]

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, xml_content.replace("enabled = TRUE", "enabled"))
        self.assertEqual(second.content, first.content)
        self.assertFalse(
            any("protected MyBatis SQL syntax changed" in item for item in first.diagnostics)
        )

    def test_xml_mybatis_preserves_fragment_grouping_but_simplifies_complete_statement(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="optionalScope">WHERE (primary_scope OR fallback_scope)</sql>\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM sample_item\n'
            '        WHERE ((missing_owner OR missing_group) AND enabled)\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            'WHERE ((missing_owner OR missing_group) AND enabled)',
            'WHERE (missing_owner OR missing_group) AND enabled',
        )
        config = Config()
        config.profile = "commit"
        config.fix = True
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-mybatis-sql", "IR-paren-same-op"]

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertIn("WHERE (primary_scope OR fallback_scope)", first.content)
        self.assertFalse(first.violations)

    def test_xml_mybatis_does_not_move_commas_across_dynamic_tags(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="dynamicOrder">\n'
            '        SELECT created_at::TIMESTAMPTZ\n'
            '        FROM utility\n'
            '        ORDER BY utility_name\n'
            '        <if test="showState">\n'
            '            , state_name\n'
            '        </if>\n'
            '    </select>\n'
            '    <select id="dynamicArgument">\n'
            '        SELECT outage_breakdown(\n'
            '            <choose>\n'
            '                <when test="byCounty">\'county\'</when>\n'
            '                <otherwise>\'state\'</otherwise>\n'
            '            </choose>, #{runStartTime})\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.disable_all = True
        config.rules_to_enable = [
            "IR-xml-mybatis-sql",
            "IR-comma-style",
            "IR-datatype-format",
        ]
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        expected = xml_content.replace(
            "created_at::TIMESTAMPTZ", "created_at::TIMESTAMP WITH TIME ZONE"
        )
        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertNotIn("utility_name,", first.content)
        self.assertIn("</choose>, #{runStartTime}", first.content)

    def test_xml_and_sql_indenters_converge_around_dynamic_blocks(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="dynamicCtes">\n'
            '        WITH base AS (\n'
            '            SELECT id, enabled, ready\n'
            '            FROM sample\n'
            '        ),\n'
            '        <if test="includeOptional">\n'
            '            optional AS (\n'
            '                SELECT id, name <if test="includeGeometry">, geom</if>\n'
            '                FROM sample\n'
            '            ),\n'
            '        </if>\n'
            '        final AS (\n'
            '            SELECT\n'
            '                CASE\n'
            '                    WHEN enabled\n'
            '                        AND ready\n'
            "                        THEN 'ready'\n"
            "                    ELSE 'waiting'\n"
            '                END AS status\n'
            '            FROM base\n'
            '        )\n'
            '        SELECT *\n'
            '        FROM final\n'
            '    </sql>\n'
            '</mapper>'
        )
        config = Config()
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(second.content, first.content)
        self.assertFalse(
            any("Formatter did not converge" in item for item in first.diagnostics)
        )
        self.assertIn(
            '                SELECT id, name <if test="includeGeometry">, geom</if>',
            first.content,
        )
        self.assertIn("            ),\n        </if>", first.content)
        self.assertIn(
            "            SELECT CASE WHEN enabled AND ready THEN 'ready' ELSE 'waiting' END AS status",
            first.content,
        )

    def test_xml_mybatis_dynamic_range_compacts_after_between_rewrite(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="bounded">\n'
            '        SELECT item_id\n'
            '        FROM sample_item\n'
            '        <if test="start != null">\n'
            '                                  WHERE recorded_timestamp_for_requested_interval &gt;= #{start} AND recorded_timestamp_for_requested_interval &lt;= #{end}\n'
            '        </if>\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(second.content, first.content)
        self.assertIn(
            '<if test="start != null">WHERE '
            "recorded_timestamp_for_requested_interval BETWEEN #{start} AND #{end}</if>",
            first.content,
        )
        self.assertNotIn("&gt;=", first.content)
        self.assertNotIn("&lt;=", first.content)
        self.assertFalse(
            any("Formatter did not converge" in item for item in first.diagnostics)
        )

    def test_xml_mybatis_long_between_wraps_before_delimiter(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="errors">\n'
            '        SELECT error_id\n'
            '        FROM sample_error\n'
            "        WHERE sample_error.recorded_timestamp &gt;= timezone('utc', '${intervalStart}') AND sample_error.recorded_timestamp &lt;= timezone('utc', '${intervalEnd}');\n"
            '    </select>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="errors">\n'
            '        SELECT error_id\n'
            '        FROM sample_error\n'
            '        WHERE\n'
            "            sample_error.recorded_timestamp BETWEEN timezone('utc', '${intervalStart}')\n"
            "                AND timezone('utc', '${intervalEnd}');\n"
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_multiline_if_uses_programming_style_boundaries(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM sample_item\n'
            '        WHERE enabled\n'
            '        <if test="filtered">        AND powered\n'
            '        AND NOT fueled</if>\n'
            '    </select>\n'
            '</mapper>\n'
        )
        expected_fragment = (
            '            <if test="filtered">\n'
            '                AND powered\n'
            '                AND NOT fueled\n'
            '            </if>'
        )
        config = Config()
        config.fix = True
        config.profile = "commit"

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertIn(expected_fragment, first.content)
        self.assertEqual(second.content, first.content)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_commit_profile_removes_implied_keywords(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT sample_item.item_id\n'
            '        FROM sample_item\n'
            '        INNER JOIN sample_state ON sample_state.state_id = sample_item.state_id\n'
            '        LEFT OUTER JOIN sample_detail ON sample_detail.item_id = sample_item.item_id\n'
            '        ORDER BY sample_item.item_id ASC;\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT sample_item.item_id\n'
            '        FROM\n'
            '            sample_item\n'
            '            JOIN sample_state ON sample_state.state_id = sample_item.state_id\n'
            '            LEFT JOIN sample_detail ON sample_detail.item_id = sample_item.item_id\n'
            '        ORDER BY sample_item.item_id;\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_select_include_uses_column_indentation(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT<include refid="Base_Column_List" />,\n'
            '        sample_item.description\n'
            '        FROM sample_item;\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT\n'
            '            <include refid="Base_Column_List" />,\n'
            '            sample_item.description\n'
            '        FROM sample_item;\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_long_join_predicate_wraps_after_operator(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT sample_error.error_id\n'
            '        FROM\n'
            '            sample_error\n'
            '            JOIN sample_error_category sample_error_category\n'
            '                ON sample_error_category.category_identifier =\n'
            '        sample_error.sample_error_category_identifier;\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT sample_error.error_id\n'
            '        FROM\n'
            '            sample_error\n'
            '            JOIN sample_error_category sample_error_category ON sample_error_category.category_identifier =\n'
            '                sample_error.sample_error_category_identifier;\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_multicondition_join_keeps_fitting_first_predicate(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT sample_item.item_id\n'
            '        FROM\n'
            '            sample_item\n'
            '            LEFT JOIN sample_customer customer ON customer.item_id = sample_item.item_id\n'
            '                AND coalesce(customer.organization_identifier, -1) = coalesce(sample_item.organization_identifier, -1);\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True
        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, xml_content)
        self.assertEqual(second.content, xml_content)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_rewrites_reversed_nullable_equality(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item.item_id\n'
            '        FROM sample_item item\n'
            '        JOIN sample_owner owner ON item.owner_id = owner.id\n'
            '            AND ((item.group_id IS NULL AND owner.group_id IS NULL) OR owner.group_id = item.group_id);\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item.item_id\n'
            '        FROM\n'
            '            sample_item item\n'
            '            JOIN sample_owner owner ON item.owner_id = owner.id\n'
            '                AND coalesce(owner.group_id, -1) = coalesce(item.group_id, -1);\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_rewrites_nullable_equality_inside_dynamic_join(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT a.item_id\n'
            '        FROM sample_item a\n'
            '        <if test="enabled">\n'
            '            JOIN sample_owner b ON a.owner_id = b.owner_id\n'
            '                AND ((a.group_id IS NULL AND b.group_id IS NULL) '
            'OR (b.group_id = a.group_id))\n'
            '        </if>\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT a.item_id\n'
            '        FROM\n'
            '            sample_item a\n'
            '            <if test="enabled">\n'
                '                JOIN sample_owner b ON a.owner_id = b.owner_id AND coalesce(b.group_id, -1) = coalesce(a.group_id, -1)\n'
            '            </if>\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_dynamic_join_after_derived_table_is_a_sibling(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM\n'
            '            sample_item item\n'
            '            JOIN (\n'
            '                    SELECT owner_id\n'
            '                    FROM sample_owner\n'
            '                ) owning ON owning.owner_id = item.owner_id\n'
            '                <if test="enabled">JOIN sample_group g ON g.owner_id = owning.owner_id</if>\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            '                <if test="enabled">',
            '            <if test="enabled">',
        )
        config = Config()
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)

    def test_xml_mybatis_nested_join_owners_do_not_cycle(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT data.item_id\n'
            '        FROM (\n'
            '                SELECT item.item_id\n'
            '                FROM\n'
            '                    sample_item item\n'
            '                    LEFT JOIN sample_owner owner ON owner.item_id = item.item_id\n'
            '                        AND coalesce(owner.group_id, -1) = coalesce(\n'
            '                            item.group_id,\n'
            '                            -1\n'
            '                        )\n'
            '            ) data\n'
            '            <if test="withTotals">\n'
            '                LEFT JOIN (\n'
            '                        SELECT item_id, count(*) AS item_count\n'
            '                        FROM sample_detail\n'
            '                        GROUP BY item_id\n'
            '                    ) totals ON totals.item_id = data.item_id\n'
            '            </if>\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        expected = xml_content.replace(
            "        FROM (\n",
            "        FROM\n            (\n",
        )

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_keeps_optional_where_condition_in_its_tag(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM sample_item\n'
            "        WHERE (#{scope} = 'ALL' IS TRUE OR scope_code = #{scope})\n"
            '        <if test="activeOnly">\n'
            '            AND active = true\n'
            '        </if>\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM sample_item\n'
            '        WHERE\n'
            "            (#{scope} = 'ALL' OR scope_code = #{scope})\n"
            '            <if test="activeOnly">AND active</if>\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_removes_whitespace_from_blank_lines(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        \n'
            '        FROM sample_item\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace('        \n', '\n')
        config = Config()
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_dynamic_logical_indent_respects_sql_grouping(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM sample_item\n'
            '        WHERE active\n'
            '        <if test="filtered">\n'
            '                    AND (owner_name = #{ownerName}\n'
            '                OR owner_code = #{ownerCode})\n'
            '        </if>\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            '                    AND (owner_name = #{ownerName}\n',
            '            AND (owner_name = #{ownerName}\n',
        )
        config = Config()
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-indent"]
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_dynamic_nested_where_aligns_boolean_conditions(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <update id="enableItems">\n'
            '        UPDATE sample_item item\n'
            '        SET enabled = TRUE\n'
            '        WHERE\n'
            '            <if test="restricted">\n'
            '                EXISTS (\n'
            '                    SELECT 1\n'
            '                    FROM sample_role role\n'
            '                    WHERE\n'
            '                        role.item_id = item.id\n'
            '                    AND role.role_name = #{roleName}\n'
            '                )\n'
            '                OR\n'
            '            </if>\n'
            '            item.owner_name IN (#{ownerName})\n'
            '    </update>\n'
            '</mapper>\n'
        )
        expected = xml_content.replace(
            '                    AND role.role_name = #{roleName}\n',
            '                        AND role.role_name = #{roleName}\n',
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_does_not_merge_optional_range_bounds(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM sample_item\n'
            '        WHERE 1 = 1\n'
            '        <if test="start != null">\n'
            '            AND recorded_at &gt;= #{start}\n'
            '        </if>\n'
            '        <if test="end != null">\n'
            '            AND recorded_at &lt;= #{end}\n'
            '        </if>\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM sample_item\n'
            '        WHERE\n'
            '            1 = 1\n'
            '            <if test="start != null">AND recorded_at &gt;= #{start}</if>\n'
            '            <if test="end != null">AND recorded_at &lt;= #{end}</if>\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)
        self.assertFalse(first.violations)

    def test_xml_mybatis_long_delete_starts_multiline_where_clause(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <update id="cleanup">\n'
            '        DELETE FROM sample_data.sample_summary_hour_max_region WHERE recorded_at &lt; #{intervalStart} AND NOT event_data;\n'
            '    </update>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <update id="cleanup">\n'
            '        DELETE FROM sample_data.sample_summary_hour_max_region\n'
            '        WHERE\n'
            '            recorded_at &lt; #{intervalStart}\n'
            '            AND NOT event_data;\n'
            '    </update>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_delete_statement_places_from_on_next_line(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <delete id="cleanup">\n'
            '        DELETE FROM sample_item\n'
            '        WHERE item_id = #{itemId}\n'
            '    </delete>\n'
            '</mapper>'
        )
        expected = xml_content.replace("DELETE FROM", "DELETE\n        FROM")
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_multicondition_where_accounts_for_from_line(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="events">\n'
            '        SELECT event_id\n'
            '        FROM sample_data.additional_processing_events\n'
            '        WHERE event_type = #{type} AND event_created_at BETWEEN #{startDate} AND #{endDate}\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="events">\n'
            '        SELECT event_id\n'
            '        FROM sample_data.additional_processing_events\n'
            '        WHERE event_type = #{type} AND event_created_at BETWEEN #{startDate} AND #{endDate}\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_foreach_continuation_expands_inline_where(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM sample_item\n'
            '        WHERE item_code IN\n'
            '            <foreach open="(" close=")" collection="codes" item="code" separator=",">#{code}</foreach>;\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM sample_item\n'
            '        WHERE\n'
            '            item_code IN\n'
            '                <foreach open="(" close=")" collection="codes" item="code" separator=",">#{code}</foreach>;\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_foreach_keeps_multicondition_where_expanded(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM sample_item\n'
            '        WHERE item_code IN\n'
            '            <foreach open="(" close=")" collection="codes" item="code" separator=",">#{code}</foreach>\n'
            '            AND enabled\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM sample_item\n'
            '        WHERE\n'
            '            item_code IN\n'
            '                <foreach open="(" close=")" collection="codes" item="code" separator=",">#{code}</foreach>\n'
            '            AND enabled\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_splits_subquery_closing_parenthesis_from_where(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM sample_item\n'
            '        <if test="ownerId != null">\n'
            '            WHERE owner_id IN (\n'
            '                SELECT owner_id\n'
            '                FROM sample_owner\n'
            '                WHERE enabled)\n'
            '        </if>\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            '                WHERE enabled)\n',
            '                WHERE enabled\n'
            '            )\n',
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_compacts_dynamic_fragment_join_opener(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="itemSource">\n'
            '        FROM\n'
            '            sample_item item\n'
            '            JOIN\n'
            '        (\n'
            '            SELECT owner_id\n'
            '            FROM sample_owner\n'
            '        ) owner ON owner.owner_id = item.owner_id\n'
            '        WHERE\n'
            '            owner.visible\n'
            '            <if test="enabledOnly">AND owner.enabled</if>\n'
            '    </sql>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="itemSource">\n'
            '        FROM\n'
            '            sample_item item\n'
            '            JOIN (\n'
            '                    SELECT owner_id\n'
            '                    FROM sample_owner\n'
            '                ) owner ON owner.owner_id = item.owner_id\n'
            '        WHERE\n'
            '            owner.visible\n'
            '            <if test="enabledOnly">AND owner.enabled</if>\n'
            '    </sql>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_repeated_join_cases_use_source_stable_layout(self):
        source = (
            "            LEFT JOIN sample_owner a ON CASE\n"
            "                    WHEN item.x IS NOT NULL THEN a.id = item.x\n"
            "                END\n"
            "            LEFT JOIN sample_owner b ON\n"
            "                CASE\n"
            "                    WHEN item.x IS NOT NULL THEN b.id = item.x\n"
            "                END\n"
        )
        expected = source.replace(
            "LEFT JOIN sample_owner a ON CASE",
            "LEFT JOIN sample_owner a ON\n                CASE",
        )

        def apply_edits(content):
            chars = list(content)
            for start, end, replacement in sorted(
                join_case_source_edits(content, (0, len(content))),
                reverse=True,
            ):
                chars[start:end] = list(replacement)
            return "".join(chars)

        fixed = apply_edits(source)
        self.assertEqual(fixed, expected)
        self.assertEqual(apply_edits(fixed), expected)

    def test_xml_mybatis_dynamic_join_continuations_and_short_subquery(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item.item_id\n'
            '        FROM\n'
            '            sample_item item\n'
            '            <if test="withRegion">\n'
            '                LEFT JOIN sample_region region\n'
            '                ON region.id = (\n'
            '                    SELECT id\n'
            '                    FROM sample_region_lookup\n'
            "                    WHERE code = 'NE')\n"
            '            </if>\n'
            '            LEFT JOIN sample_detail detail ON detail.item_id = item.item_id\n'
            '            AND detail.active\n'
            '            AND\n'
            '            <if test="withRegion">detail.region_id = region.id</if>\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item.item_id\n'
            '        FROM\n'
            '            sample_item item\n'
            '            <if test="withRegion">\n'
            '                LEFT JOIN sample_region region\n'
            "                    ON region.id = (SELECT id FROM sample_region_lookup WHERE code = 'NE')\n"
            '            </if>\n'
            '            LEFT JOIN sample_detail detail ON detail.item_id = item.item_id AND detail.active AND\n'
            '            <if test="withRegion">detail.region_id = region.id</if>\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_between_layout_uses_physical_source_width(self):
        indent = " " * 20
        source = (
            indent
            + "WHERE sample.recorded_at BETWEEN #{rangeStart} AND #{rangeEnd}"
        )
        sql_text = source
        mapping = list(range(len(source)))
        expected = source.replace(" AND #{rangeEnd}", "\n" + indent + "    AND #{rangeEnd}")

        def apply_edits(content):
            chars = list(content)
            for start, end, replacement in sorted(
                between_delimiter_source_edits(
                    sql_text,
                    mapping,
                    content,
                    (0, len(content)),
                    [(0, len(content), len(indent))],
                    {"max_length": 70},
                ),
                reverse=True,
            ):
                chars[start:end] = list(replacement)
            return "".join(chars)

        self.assertEqual(apply_edits(source), expected)

    def test_xml_mybatis_preserves_dynamic_in_subquery_layout(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM sample_item\n'
            '        WHERE\n'
            '            enabled\n'
            '            AND county_id IN (\n'
            '                SELECT county_id\n'
            '                FROM sample_county\n'
            '                WHERE county_code IN '\
            '<foreach collection="codes" item="code" open="(" close=")" separator=",">#{code}</foreach>\n'
            '            )\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM sample_item\n'
            '        WHERE\n'
            '            enabled\n'
            '            AND county_id IN (\n'
            '                SELECT county_id\n'
            '                FROM sample_county\n'
            '                WHERE\n'
            '                    county_code IN\n'
            '                        <foreach collection="codes" item="code" open="(" close=")" separator=",">#{code}</foreach>\n'
            '            )\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_reanchors_static_subquery_lines_after_dynamic_tag(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM (\n'
            '                SELECT item_id\n'
            '                FROM sample_item\n'
            '                WHERE\n'
            '                    enabled\n'
            '                    <if test="ownerId != null">AND owner_id = #{ownerId}</if>\n'
            '        AND visible\n'
            '        ORDER BY item_id\n'
            '        <if test="limit != null">LIMIT #{limit}</if>\n'
            '            ) visible_item\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM (\n'
            '                SELECT item_id\n'
            '                FROM sample_item\n'
            '                WHERE\n'
            '                    enabled\n'
            '                    <if test="ownerId != null">AND owner_id = #{ownerId}</if>\n'
            '                    AND visible\n'
            '                ORDER BY item_id\n'
            '                <if test="limit != null">LIMIT #{limit}</if>\n'
            '            ) visible_item\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_reanchors_static_clauses_after_dynamic_projection(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item.item_id\n'
            '        FROM\n'
            '            sample_item item\n'
            '            JOIN (\n'
            '                    SELECT\n'
            '                        owner.owner_id,\n'
            '                        <if test="withCode">owner.owner_code</if>\n'
            '\n'
            '                FROM sample_owner owner\n'
            '        WHERE owner.enabled\n'
            '        UNION\n'
            '                    SELECT archived_owner_id\n'
            '                    FROM archived_owner\n'
            '                ) owners ON owners.owner_id = item.owner_id\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            '\n                FROM sample_owner owner\n'
            '        WHERE owner.enabled\n'
            '        UNION\n',
            '                    FROM sample_owner owner\n'
            '                    WHERE owner.enabled\n'
            '                    UNION\n',
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_shared_clauses_do_not_inherit_choose_branch_indent(self):
        self.maxDiff = None
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM (\n'
            '            <choose>\n'
            '                <when test="archived">\n'
            '                    SELECT item_id, owner_id\n'
            '                    FROM archived_item\n'
            '                </when>\n'
            '                <otherwise>\n'
            '                    SELECT item_id, owner_id\n'
            '                    FROM current_item\n'
            '                </otherwise>\n'
            '            </choose>\n'
            '                    JOIN sample_owner owner ON owner.owner_id = item_id\n'
            '                    LEFT JOIN sample_group item_group ON item_group.owner_id = owner.owner_id\n'
            '                        AND item_group.enabled\n'
            '                WHERE owner.enabled\n'
            '                GROUP BY item_id\n'
            '        ) items\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            '                    JOIN sample_owner',
            '                JOIN sample_owner',
        ).replace(
            '                    LEFT JOIN sample_group',
            '                LEFT JOIN sample_group',
        ).replace(
            '                        AND item_group.enabled',
            '                    AND item_group.enabled',
        ).replace(
            '                WHERE owner.enabled',
            '            WHERE owner.enabled',
        ).replace(
            '                GROUP BY item_id',
            '            GROUP BY item_id',
        ).replace(
            '                LEFT JOIN sample_group item_group ON item_group.owner_id = owner.owner_id\n'
            '                    AND item_group.enabled',
            '                LEFT JOIN sample_group item_group ON item_group.owner_id = owner.owner_id AND item_group.enabled',
        )
        config = Config()
        config.profile = "commit"
        config.disable_all = True
        config.rules_to_enable = [
            "IR-xml-mybatis-sql",
            "IR-from-multi",
            "IR-join-on-multi",
            "IR-clause-alignment",
        ]
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_shared_from_choice_aligns_following_clauses(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM\n'
            '            <choose>\n'
            '                <when test="archived">archived_item item</when>\n'
            '                <otherwise>current_item item</otherwise>\n'
            '            </choose>\n'
            '                JOIN sample_owner owner ON owner.owner_id = item.owner_id\n'
            '            WHERE owner.enabled\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            '                JOIN sample_owner',
            '            JOIN sample_owner',
        ).replace(
            '            WHERE owner.enabled',
            '        WHERE owner.enabled',
        )
        config = Config()
        config.profile = "commit"
        config.disable_all = True
        config.rules_to_enable = [
            "IR-xml-mybatis-sql",
            "IR-from-multi",
            "IR-join-on-multi",
            "IR-clause-alignment",
        ]
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_complete_query_choice_aligns_shared_joins(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        WITH selected_items AS (\n'
            '            <choose>\n'
            '                <when test="archived">\n'
            '                    SELECT item_id, owner_id\n'
            '                    FROM archived_item\n'
            '                </when>\n'
            '                <otherwise>\n'
            '                    SELECT item_id, owner_id\n'
            '                    FROM current_item\n'
            '                </otherwise>\n'
            '            </choose>\n'
            '                JOIN sample_owner owner ON owner.owner_id = owner_id\n'
            '            WHERE owner.enabled\n'
            '        )\n'
            '        SELECT item_id\n'
            '        FROM selected_items\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            '                JOIN sample_owner',
            '            JOIN sample_owner',
        )
        config = Config()
        config.profile = "commit"
        config.disable_all = True
        config.rules_to_enable = [
            "IR-xml-mybatis-sql",
            "IR-from-multi",
            "IR-join-on-multi",
            "IR-clause-alignment",
        ]
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_dynamic_branch_keeps_sql_inside_tag(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        WITH selected_items AS (\n'
            '            SELECT item_id\n'
            '            FROM current_item\n'
            '            UNION ALL\n'
            '            <choose>\n'
            '                <when test="archived">\n'
            '        SELECT item_id\n'
            '        FROM\n'
            '                        archived_item\n'
            '        WHERE archived\n'
            '                </when>\n'
            '            </choose>\n'
            '        )\n'
            '        SELECT item_id\n'
            '        FROM selected_items\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            '        SELECT item_id\n'
            '        FROM\n',
            '                    SELECT item_id\n'
            '                    FROM\n',
        ).replace(
            '        WHERE archived',
            '                    WHERE archived',
        )
        config = Config()
        config.profile = "commit"
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-mybatis-sql"]
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_aligned_dynamic_set_branch_stays_inside_tag(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        WITH selected_items AS (\n'
            '            SELECT item_id\n'
            '            FROM current_item\n'
            '            UNION ALL\n'
            '            <choose>\n'
            '                <when test="archived">\n'
            '                    SELECT item_id\n'
            '                    FROM archived_item\n'
            '                    WHERE archived\n'
            '                </when>\n'
            '            </choose>\n'
            '        )\n'
            '        SELECT item_id\n'
            '        FROM selected_items\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.disable_all = True
        config.rules_to_enable = [
            "IR-xml-mybatis-sql",
            "IR-clause-alignment",
        ]
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, xml_content)
        self.assertEqual(second.content, xml_content)
        self.assertFalse(first.diagnostics)
        self.assertFalse(second.diagnostics)

    def test_xml_mybatis_dynamic_set_branch_survives_semantic_convergence(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        WITH selected_items AS (\n'
            '            SELECT item_id, ARRAY[]::int[] AS item_values\n'
            '            FROM current_item\n'
            '            UNION ALL\n'
            '            -- optional archived items\n'
            '            <choose>\n'
            '                <when test="archived">\n'
            '                    SELECT item_id, ARRAY[]::int[] AS item_values\n'
            '                    FROM archived_item\n'
            '                    WHERE archived\n'
            '                </when>\n'
            '            </choose>\n'
            '        )\n'
            '        SELECT item_id\n'
            '        FROM selected_items\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace("::int[]", "::INTEGER[]")
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)
        self.assertFalse(second.diagnostics)

    def test_xml_mybatis_formats_dynamic_window_ordering(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <insert id="items">\n'
            '        INSERT INTO sample_item (\n'
            '                item_id,\n'
            '                row_number\n'
            '            )\n'
            '            SELECT\n'
            '                item_id,\n'
            '                row_number() OVER (ORDER BY\n'
            '                <choose>\n'
            '                    <when test="orderByName">item_name, item_id</when>\n'
            '                    <when test="orderByAll">\n'
            '                            item_name, item_state, item_region, item_count, recorded_at, item_id\n'
            '                    </when>\n'
            '                </choose>\n'
            '                )\n'
            '            FROM sample_item\n'
            '    </insert>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <insert id="items">\n'
            '        INSERT INTO sample_item (\n'
            '            item_id,\n'
            '            row_number\n'
            '        )\n'
            '            SELECT\n'
            '                item_id,\n'
            '                row_number() OVER (\n'
            '                    ORDER BY\n'
            '                        <choose>\n'
            '                            <when test="orderByName">item_name, item_id</when>\n'
            '                            <when test="orderByAll">\n'
            '                                item_name, item_state, item_region, item_count, recorded_at, item_id\n'
            '                            </when>\n'
            '                        </choose>\n'
            '                )\n'
            '            FROM sample_item\n'
            '    </insert>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)
        self.assertFalse(second.diagnostics)

    def test_xml_mybatis_include_semantics_do_not_starve_host_layout(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="sourceItems">\n'
            '        SELECT item_id, null::int AS item_count\n'
            '        FROM sample_item\n'
            '        WHERE owner_id = #{ownerId}\n'
            '    </sql>\n'
            '    <insert id="copyItems">\n'
            '        INSERT INTO copied_item (\n'
            '                item_id\n'
            '            )\n'
            '            <include refid="sourceItems" />\n'
            '    </insert>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="sourceItems">\n'
            '        SELECT item_id, null::INTEGER AS item_count\n'
            '        FROM sample_item\n'
            '        WHERE owner_id = #{ownerId}\n'
            '    </sql>\n'
            '    <insert id="copyItems">\n'
            '        INSERT INTO copied_item (item_id)\n'
            '        <include refid="sourceItems" />\n'
            '    </insert>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)
        self.assertFalse(second.diagnostics)

    def test_xml_mybatis_case_continuation_inside_choose_converges(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        <choose>\n'
            '            <when test="active">\n'
            '                SELECT\n'
            '                    CASE\n'
            '                        WHEN item.active\n'
            '                            AND item.visible\n'
            '                            THEN item.item_id\n'
            '                    END\n'
            '                FROM sample_item item\n'
            '            </when>\n'
            '        </choose>\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        expected = xml_content.replace(
            '                SELECT\n'
            '                    CASE\n'
            '                        WHEN item.active\n'
            '                            AND item.visible\n'
            '                            THEN item.item_id\n'
            '                    END',
            '                SELECT CASE WHEN item.active AND item.visible THEN item.item_id END',
        )

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)
        self.assertFalse(second.diagnostics)

    def test_xml_mybatis_repeated_foreach_uses_expanded_layout_consistently(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM sample_item\n'
            '        WHERE primary_code IN\n'
            '            <foreach collection="codes" item="code" open="(" close=")" separator=",">\n'
            '                #{code}\n'
            '            </foreach>\n'
            '            OR secondary_code IN\n'
            '            <foreach collection="codes" item="code" open="(" close=")" separator=",">#{code}</foreach>\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM sample_item\n'
            '        WHERE\n'
            '            primary_code IN\n'
            '                <foreach collection="codes" item="code" open="(" close=")" separator=",">\n'
            '                    #{code}\n'
            '                </foreach>\n'
            '            OR secondary_code IN\n'
            '                <foreach collection="codes" item="code" open="(" close=")" separator=",">\n'
            '                    #{code}\n'
            '                </foreach>\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-indent", "IR-xml-line-length"]
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)
        self.assertFalse(second.diagnostics)

    def test_xml_mybatis_commit_profile_expands_datatype_aliases(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="types">\n'
            '        SELECT NULL::INT, NULL::INT8, NULL::BOOL, NULL::FLOAT8, NULL::TIMETZ;\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            "NULL::INT, NULL::INT8, NULL::BOOL, NULL::FLOAT8, NULL::TIMETZ",
            "NULL::INTEGER, NULL::BIGINT, NULL::BOOLEAN, NULL::DOUBLE PRECISION, NULL::TIME WITH TIME ZONE",
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_commit_profile_compacts_normalized_simple_case(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="summary">\n'
            '        SELECT\n'
            '                                    CASE WHEN (sum(override_count) IS NULL) THEN false ELSE true END AS has_override\n'
            '        FROM sample_summary\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            '        SELECT\n'
            '                                    CASE WHEN (sum(override_count) IS NULL) THEN false ELSE true END AS has_override',
            '        SELECT CASE WHEN (sum(override_count) IS NULL) THEN false ELSE true END AS has_override',
        )
        config = Config()
        config.profile = "commit"
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-mybatis-sql", "IR-case"]
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_formats_adjacent_complete_if_queries(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="branchQueries">\n'
            '        WITH selected_item AS (\n'
            '            <if test="current">\n'
            '                SELECT item_id, owner_id, item_name\n'
            '                FROM current_item item JOIN sample_owner owner ON owner.owner_id = item.owner_id\n'
            '            </if>\n'
            '            <if test="archived">\n'
            '                SELECT item_id, owner_id, item_name\n'
            '                FROM archived_item item JOIN sample_owner owner ON owner.owner_id = item.owner_id\n'
            '            </if>\n'
            '        )\n'
            '        SELECT * FROM selected_item\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="branchQueries">\n'
            '        WITH selected_item AS (\n'
            '            <if test="current">\n'
            '                SELECT item_id, owner_id, item_name\n'
            '                FROM\n'
            '                    current_item item\n'
            '                    JOIN sample_owner owner ON owner.owner_id = item.owner_id\n'
            '            </if>\n'
            '            <if test="archived">\n'
            '                SELECT item_id, owner_id, item_name\n'
            '                FROM\n'
            '                    archived_item item\n'
            '                    JOIN sample_owner owner ON owner.owner_id = item.owner_id\n'
            '            </if>\n'
            '        )\n'
            '        SELECT * FROM selected_item\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_conflict_update_formats_set_assignments(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <insert id="saveState">\n'
            '        INSERT INTO sample_state (state_key, state_value, updated_at)\n'
            '        VALUES (#{key}, #{value}, now())\n'
            '        ON CONFLICT (state_key) DO UPDATE\n'
            '        SET state_value = excluded.state_value,\n'
            '            updated_at = excluded.updated_at\n'
            '    </insert>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            "        SET state_value = excluded.state_value,",
            "        SET\n            state_value = excluded.state_value,",
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_multiline_update_starts_set_on_its_own_line(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <update id="copyValue">\n'
            '        UPDATE sample_item item SET\n'
            '            item_value = source.item_value\n'
            '        FROM sample_source source\n'
            '        WHERE source.item_id = item.item_id AND item.item_value != source.item_value;\n'
            '    </update>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            '        UPDATE sample_item item SET\n            item_value',
            '        UPDATE sample_item item\n        SET item_value',
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_update_from_relations_do_not_expand_single_set_assignment(self):
        sql_content = (
            "UPDATE sample_target AS target\n"
            "SET target_value = source.source_value\n"
            "FROM\n"
            "    sample_source AS source,\n"
            "    sample_scope AS scope\n"
            "WHERE source.scope_id = scope.id AND target.id = source.target_id;\n"
        )
        config = Config()
        config.profile = "commit"
        config.fix = True
        expected = sql_content.replace(" AS source", " source").replace(
            " AS scope", " scope"
        )

        first = process_document(config, sql_content, "generic.sql", "sql")
        second = process_document(
            config, first.content, "generic.sql", "sql"
        )

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_long_select_with_addition_does_not_cycle_layout(self):
        sql_content = (
            "SELECT 2024, 101, 'North District', 'ND', 1000, 2000, "
            "3000, 4000, 5000, 6000, 'PREFIX_' || 101 || '_ND'\n"
            "FROM sample_inventory;\n"
        )
        expected = (
            "SELECT\n"
            "    2024,\n"
            "    101,\n"
            "    'North District',\n"
            "    'ND',\n"
            "    1000,\n"
            "    2000,\n"
            "    3000,\n"
            "    4000,\n"
            "    5000,\n"
            "    6000,\n"
            "    'PREFIX_' || 101\n"
            "        || '_ND'\n"
            "FROM sample_inventory;\n"
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, sql_content, "generic.sql", "sql")
        second = process_document(
            config, first.content, "generic.sql", "sql"
        )

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_where_case_comparison_continuation_does_not_cycle(self):
        sql_content = (
            "SELECT item_id\n"
            "FROM sample_item\n"
            "WHERE\n"
            "    CASE\n"
            "        WHEN grouping_mode =\n"
            "            'regional'\n"
            "            AND very_long_owner_identifier IS NULL\n"
            "            AND very_long_region_identifier IS NOT NULL\n"
            "            AND another_long_scope_identifier IS NOT NULL\n"
            "            THEN TRUE\n"
            "        ELSE FALSE\n"
            "    END\n"
            "    AND active;\n"
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, sql_content, "generic.sql", "sql")
        second = process_document(
            config, first.content, "generic.sql", "sql"
        )

        self.assertEqual(first.content, sql_content)
        self.assertEqual(second.content, sql_content)
        self.assertFalse(first.diagnostics)

    def test_multiline_case_keeps_additive_condition_continuation(self):
        sql_content = (
            "SELECT\n"
            "    CASE\n"
            "        WHEN previous_time = current_time + INTERVAL '15 minutes' THEN current_time\n"
            "        ELSE current_time + INTERVAL '1 hour'\n"
            "    END AS adjusted_time\n"
            "FROM sample_event;\n"
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, sql_content, "generic.sql", "sql")
        second = process_document(
            config, first.content, "generic.sql", "sql"
        )

        self.assertEqual(first.content, sql_content)
        self.assertEqual(second.content, sql_content)
        self.assertFalse(first.diagnostics)

    def test_multiline_case_rejoins_short_else_result(self):
        sql_content = (
            "SELECT\n"
            "    CASE\n"
            "        WHEN enabled\n"
            "            THEN first_count + second_count\n"
            "                + third_count + fourth_count\n"
            "        ELSE\n"
            "            0\n"
            "    END AS total_count\n"
            "FROM sample_record;\n"
        )
        expected = (
            "SELECT\n"
            "    CASE\n"
            "        WHEN enabled THEN first_count + second_count\n"
            "            + third_count + fourth_count\n"
            "        ELSE 0\n"
            "    END AS total_count\n"
            "FROM sample_record;\n"
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, sql_content, "generic.sql", "sql")
        second = process_document(
            config, first.content, "generic.sql", "sql"
        )

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_simple_case_result_continuation_does_not_cycle_then_layout(self):
        sql_content = (
            "SELECT\n"
            "    CASE\n"
            "        category\n"
            "        WHEN 'bounded'\n"
            "            THEN lower_value IS NOT NULL\n"
            "                AND upper_value IS NOT NULL\n"
            "                AND lower_value <= upper_value\n"
            "        ELSE FALSE\n"
            "    END AS valid_range\n"
            "FROM sample_record;\n"
        )
        expected = sql_content.replace(
            "        WHEN 'bounded'\n            THEN",
            "        WHEN 'bounded' THEN",
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, sql_content, "generic.sql", "sql")
        second = process_document(
            config, first.content, "generic.sql", "sql"
        )

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_multiline_case_condition_rebases_nested_expression_indent(self):
        sql_content = (
            "SELECT\n"
            "    CASE\n"
            "        WHEN error_count >\n"
            "    ((abs(\n"
            "        extract(\n"
            "            epoch FROM (cast(interval_start AS TIMESTAMP)\n"
            "    - cast(interval_end AS TIMESTAMP))\n"
            "        ) / 3600\n"
            "    ) * 4) / 2)\n"
            "            THEN 'unstable'\n"
            "        ELSE 'normal'\n"
            "    END AS status\n"
            "FROM sample_record;\n"
        )
        expected = (
            "SELECT\n"
            "    CASE\n"
            "        WHEN error_count >\n"
            "            ((abs(\n"
            "                extract(\n"
            "                    epoch FROM (cast(interval_start AS TIMESTAMP)\n"
            "                        - cast(interval_end AS TIMESTAMP))\n"
            "                ) / 3600\n"
            "            ) * 4) / 2)\n"
            "            THEN 'unstable'\n"
            "        ELSE 'normal'\n"
            "    END AS status\n"
            "FROM sample_record;\n"
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, sql_content, "generic.sql", "sql")
        second = process_document(
            config, first.content, "generic.sql", "sql"
        )

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_case_condition_defers_scalar_subquery_indentation(self):
        sql_content = (
            "SELECT\n"
            "    CASE\n"
            "        WHEN current_measurement_score >= (\n"
            "            SELECT max(historical_measurement_score)\n"
            "            FROM sample_measurement_history_for_current_reporting_period\n"
            "        )\n"
            "            THEN 'above the historical measurement threshold'\n"
            "        ELSE 'within the historical measurement threshold'\n"
            "    END AS measurement_status\n"
            "FROM sample_measurement_record;\n"
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, sql_content, "generic.sql", "sql")
        second = process_document(
            config, first.content, "generic.sql", "sql"
        )

        self.assertEqual(first.content, sql_content)
        self.assertEqual(second.content, sql_content)
        self.assertFalse(first.diagnostics)

    def test_case_layout_does_not_rebuild_procedural_statement_bodies(self):
        sql_content = (
            "CASE report_scope\n"
            "    WHEN 'active' THEN\n"
            "        RETURN QUERY\n"
            "        SELECT id\n"
            "        FROM sample_record\n"
            "        WHERE enabled;\n"
            "    ELSE\n"
            "        RETURN QUERY\n"
            "        SELECT id FROM sample_record;\n"
            "END CASE;\n"
        )
        config = Config()
        config.profile = "commit"
        config.fix = True
        config.disable_all = True
        config.rules_to_enable = ["IR-case"]

        result = process_document(config, sql_content, "generic.sql", "sql")

        self.assertEqual(result.content, sql_content)
        self.assertFalse(result.diagnostics)

    def test_commit_profile_aligns_parenthesized_where_predicates(self):
        sql_content = (
            "SELECT item_id\n"
            "FROM sample_item\n"
            "WHERE\n"
            "    active\n"
            "    AND (\n"
            "        requested_owner_name ILIKE '%' || owner_filter || '%'\n"
            "            OR requested_owner_identifier::TEXT ILIKE '%' || owner_filter || '%'\n"
            "    );\n"
        )
        expected = sql_content.replace("            OR", "        OR")
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, sql_content, "generic.sql", "sql")
        second = process_document(
            config, first.content, "generic.sql", "sql"
        )

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_multiline_update_is_not_recompacted_after_expression_wrap(self):
        sql_content = (
            "UPDATE sample_group\n"
            "SET generated_key = lower(substring(group_name, 1, 1))\n"
            "    || substring(replace(group_name, ' ', ''), 2);\n"
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, sql_content, "generic.sql", "sql")
        second = process_document(
            config, first.content, "generic.sql", "sql"
        )

        self.assertEqual(first.content, sql_content)
        self.assertEqual(second.content, sql_content)
        self.assertFalse(first.diagnostics)

    def test_update_compaction_respects_additive_line_limit(self):
        sql_content = (
            "UPDATE sample_provider_group\n"
            "SET generated_key = lower(substring(group_name, 1, 1)) "
            "|| substring(replace(group_name, ' ', ''), 2);\n"
        )
        expected = sql_content.replace(
            ")) || substring", "))\n    || substring"
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, sql_content, "generic.sql", "sql")
        second = process_document(
            config, first.content, "generic.sql", "sql"
        )

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_trailing_subtraction_operator_moves_to_the_continuation(self):
        sql_content = (
            "SELECT ((date_part('epoch', current_interval_start_timestamp_with_timezone_value) -\n"
            "date_part('epoch', previous_interval_end_timestamp_with_timezone_value)) / 3600;\n"
        )
        expected = (
            "SELECT\n"
            "    ((date_part('epoch', current_interval_start_timestamp_with_timezone_value)\n"
            "        - date_part('epoch', previous_interval_end_timestamp_with_timezone_value)) / 3600;\n"
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, sql_content, "generic.sql", "sql")
        second = process_document(
            config, first.content, "generic.sql", "sql"
        )

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_short_filter_where_predicate_compacts_to_one_line(self):
        sql_content = (
            "SELECT\n"
            "    count(*) FILTER (\n"
            "        WHERE activity.state = 'active'\n"
            "          AND activity.pid != pg_backend_pid()\n"
            "    ) AS active_query_count\n"
            "FROM pg_stat_activity activity;\n"
        )
        expected = sql_content.replace(
            "activity.state = 'active'\n          AND",
            "activity.state = 'active' AND",
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, sql_content, "generic.sql", "sql")
        second = process_document(
            config, first.content, "generic.sql", "sql"
        )

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_nested_filter_parenthesis_tracks_its_expression_indent(self):
        sql_content = (
            "SELECT\n"
            "    coalesce(\n"
            "        max(value) FILTER (\n"
            "        WHERE active AND current\n"
            "    ),\n"
            "        0\n"
            "    ) AS current_value\n"
            "FROM sample_record;\n"
        )
        expected = sql_content.replace(
            "        WHERE active AND current\n    ),",
            "            WHERE active AND current\n        ),",
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, sql_content, "generic.sql", "sql")
        second = process_document(
            config, first.content, "generic.sql", "sql"
        )

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_dynamic_where_formats_parenthesized_or_arms(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="boundedRecords">\n'
            '        SELECT record_id\n'
            '        FROM sample_record\n'
            '        <if test="bounded">\n'
            '            WHERE\n'
            '            (\n'
            '                record_table.record_start &gt;= #{start}\n'
            '                AND record_table.record_start &lt;= #{end}\n'
            '            )\n'
            '                OR\n'
            '            (\n'
            '            record_table.extraordinarily_long_record_completion_timestamp IS NOT NULL\n'
            '                AND record_table.extraordinarily_long_record_completion_timestamp BETWEEN #{start} AND #{end}\n'
            '            )\n'
            '        </if>\n'
            '    </select>\n'
            '</mapper>\n'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="boundedRecords">\n'
            '        SELECT record_id\n'
            '        FROM sample_record\n'
            '        <if test="bounded">\n'
            '            WHERE\n'
            '                record_table.record_start BETWEEN #{start} AND #{end}\n'
            '                OR (\n'
            '                    record_table.extraordinarily_long_record_completion_timestamp IS NOT NULL\n'
            '                    AND record_table.extraordinarily_long_record_completion_timestamp BETWEEN #{start} AND #{end}\n'
            '                )\n'
            '        </if>\n'
            '    </select>\n'
            '</mapper>\n'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(
            config, first.content, "generic.xml", "xml"
        )

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_short_update_clauses_compact_when_expressions_are_single_line(self):
        sql_content = (
            "UPDATE sample_record\n"
            "SET processed_at = now()\n"
            "WHERE enabled AND processed_at IS NULL;\n"
        )
        expected = (
            "UPDATE sample_record SET processed_at = now() "
            "WHERE enabled AND processed_at IS NULL;\n"
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, sql_content, "generic.sql", "sql")
        second = process_document(
            config, first.content, "generic.sql", "sql"
        )

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_dynamic_boundary_does_not_capture_following_where(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM\n'
            '            <choose>\n'
            '                <when test="archived">archived_item</when>\n'
            '                <otherwise>sample_item</otherwise>\n'
            '            </choose> item\n'
            '        WHERE\n'
            '            item.recorded_at BETWEEN #{start} AND #{end}\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            "        WHERE\n            item.recorded_at",
            "        WHERE item.recorded_at",
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_multicolumn_if_remains_expanded(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT\n'
            '            item_id,\n'
            '            <if test="includeDetails">\n'
            '                detail_code,\n'
            '                detail_name,\n'
            '            </if>\n'
            '            item_name\n'
            '        FROM sample_item;\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, xml_content)
        self.assertEqual(second.content, xml_content)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_dynamic_distinct_on_uses_multiline_keys(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT DISTINCT ON (recorded_at, organization_id,\n'
            '        <if test="includeRegion">region_id,</if>\n'
            '            coalesce(category_id, -1))\n'
            '            *\n'
            '        FROM sample_item;\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT\n'
            '            DISTINCT ON (\n'
            '                recorded_at,\n'
            '                organization_id,\n'
            '                <if test="includeRegion">region_id,</if>\n'
            '                coalesce(category_id, -1)\n'
            '            ) *\n'
            '        FROM sample_item;\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_preserves_reviewed_dynamic_distinct_layout(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT\n'
            '            DISTINCT ON (\n'
            '                recorded_at,\n'
            '                organization_id,\n'
            '                <if test="includeRegion">region_id,</if>\n'
            '                coalesce(category_id, -1)\n'
            '            ) *\n'
            '        FROM sample_item;\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, xml_content)
        self.assertEqual(second.content, xml_content)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_nested_dynamic_where_keeps_cte_indentation(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        WITH filtered_items AS (\n'
            '            SELECT item_id\n'
            '            FROM sample_item\n'
            '            WHERE\n'
            '                recorded_at BETWEEN #{start} AND #{end}\n'
            '                AND active\n'
            '                <if test="organizationId != null">\n'
            '                    AND organization_id = #{organizationId}\n'
            '                </if>\n'
            '        )\n'
            '        SELECT item_id\n'
            '        FROM filtered_items;\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True
        expected = xml_content.replace(
            '                <if test="organizationId != null">\n'
            '                    AND organization_id = #{organizationId}\n'
            '                </if>',
            '                <if test="organizationId != null">AND organization_id = #{organizationId}</if>',
        )

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_dynamic_cte_select_branches_keep_xml_indentation(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        WITH filtered_items AS (\n'
            '            <if test="byOwner">\n'
            '                SELECT owner_id\n'
            '                FROM sample_owner\n'
            '                WHERE\n'
            '                    active\n'
            '                    AND visible\n'
            '            </if>\n'
            '            <if test="byGroup">\n'
            '                SELECT owner_id\n'
            '                FROM sample_group_owner\n'
            '                WHERE\n'
            '                    active\n'
            '                    AND visible\n'
            '            </if>\n'
            '        )\n'
            '        SELECT owner_id\n'
            '        FROM filtered_items;\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, xml_content)
        self.assertEqual(second.content, xml_content)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_dynamic_cte_formats_function_and_additive_indentation(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        WITH totals AS (\n'
            '            <if test="included">\n'
            '                SELECT\n'
            '                    coalesce(\n'
            '                total_count,\n'
            '                        residential_count + transportation_count\n'
            '                  + commercial_count + industrial_count\n'
            '            ) AS covered_count\n'
            '                FROM sample_count\n'
            '            </if>\n'
            '        )\n'
            '        SELECT covered_count FROM totals;\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        WITH totals AS (\n'
            '            <if test="included">\n'
            '                SELECT\n'
            '                    coalesce(\n'
            '                        total_count,\n'
            '                        residential_count + transportation_count\n'
            '                            + commercial_count + industrial_count\n'
            '                    ) AS covered_count\n'
            '                FROM sample_count\n'
            '            </if>\n'
            '        )\n'
            '        SELECT covered_count FROM totals;\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_formats_optional_complete_select_columns(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_identifier, owner_identifier,\n'
            '        <if test="includeRegion">\n'
            '            region_identifier,\n'
            '            region_display_name,\n'
            '        </if>\n'
            '        recorded_timestamp, updated_timestamp, created_timestamp\n'
            '        FROM sample_item;\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT\n'
            '            item_identifier,\n'
            '            owner_identifier,\n'
            '            <if test="includeRegion">\n'
            '                region_identifier,\n'
            '                region_display_name,\n'
            '            </if>\n'
            '            recorded_timestamp,\n'
            '            updated_timestamp,\n'
            '            created_timestamp\n'
            '        FROM sample_item;\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_maps_dynamic_join_continuation_indentation(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item.item_identifier\n'
            '        FROM sample_item_with_a_descriptive_name item\n'
            '        <if test="includeOwner">\n'
            '            LEFT JOIN sample_owner_with_a_descriptive_name owner '
            'ON owner.organization_identifier = item.organization_identifier\n'
            '            AND owner.external_identifier = item.owner_external_identifier\n'
            '        </if>\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            '            LEFT JOIN sample_owner_with_a_descriptive_name owner '
            'ON owner.organization_identifier = item.organization_identifier\n'
            '            AND owner.external_identifier',
            '            LEFT JOIN sample_owner_with_a_descriptive_name owner\n'
            '                ON owner.organization_identifier = item.organization_identifier\n'
            '                AND owner.external_identifier',
        ).replace(
            '        FROM sample_item_with_a_descriptive_name item\n',
            '        FROM\n'
            '            sample_item_with_a_descriptive_name item\n',
        ).replace(
            '        <if test="includeOwner">\n'
            '            LEFT JOIN',
            '            <if test="includeOwner">\n'
            '                LEFT JOIN',
        ).replace(
            '                ON owner.organization_identifier',
            '                    ON owner.organization_identifier',
        ).replace(
            '                AND owner.external_identifier',
            '                    AND owner.external_identifier',
        ).replace(
            '        </if>\n',
            '            </if>\n',
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_preserves_repeated_nested_select_keywords(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="nestedItems">\n'
            '        SELECT wrapper.item_identifier\n'
            '        FROM (\n'
            '                 select first_item.item_identifier\n'
            '                 from sample_first_item first_item\n'
            '                 UNION\n'
            '                 select second_item.item_identifier\n'
            '                 from sample_second_item second_item\n'
            '                 UNION\n'
            '                 select third_item.item_identifier\n'
            '                 from sample_third_item third_item\n'
            '             ) wrapper\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content.count("SELECT"), 4)
        self.assertEqual(second.content, first.content)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_static_nested_query_applies_atomic_layout(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="nestedItems">\n'
            '        select wrapper.item_id from (\n'
            '        select item_id from sample_first\n'
            '        union all\n'
            '        select item_id from sample_second\n'
            '        union all\n'
            '        select item_id from sample_third\n'
            '        ) wrapper where wrapper.item_id is not null\n'
            '    </select>\n'
            '</mapper>\n'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertIn("        SELECT wrapper.item_id", first.content)
        self.assertIn("        FROM (", first.content)
        self.assertIn("                SELECT item_id", first.content)
        self.assertIn("        WHERE wrapper.item_id", first.content)
        self.assertEqual(second.content, first.content)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_formats_dynamic_group_by_items(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="groupedItems">\n'
            '        SELECT count(*)\n'
            '        FROM sample_item item\n'
            '        GROUP BY item.organization_identifier, item.owner_identifier,\n'
            '        <if test="byState">item.state_identifier</if>\n'
            '        <if test="byCounty">item.county_identifier, item.state_identifier</if>\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            '        GROUP BY item.organization_identifier, item.owner_identifier,\n',
            '        GROUP BY\n'
            '            item.organization_identifier,\n'
            '            item.owner_identifier,\n',
        ).replace(
            '        <if test="byState">',
            '            <if test="byState">',
        ).replace(
            '        <if test="byCounty">',
            '            <if test="byCounty">',
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_compacts_short_dynamic_order_by_suffix(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="orderedItems">\n'
            '        SELECT item_identifier\n'
            '        FROM sample_item\n'
            '        ORDER BY item_name\n'
            '        <if test="byLocation">\n'
            '            , state_code, county_name\n'
            '        </if>\n'
            '        ;\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="orderedItems">\n'
            '        SELECT item_identifier\n'
            '        FROM sample_item\n'
            '        ORDER BY item_name '
            '<if test="byLocation">, state_code, county_name</if>;\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_removes_sql_trailing_whitespace(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="calculatedItems">\n'
            '        SELECT item_count +   \n'
            '            CASE WHEN enabled THEN 1 ELSE 0 END AS adjusted_count\n'
            '        FROM sample_item\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            'item_count +   \n            CASE',
            'item_count + CASE',
        )
        config = Config()
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_maps_keyword_case_inside_dynamic_predicate(self):
        self.maxDiff = None
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="filteredItems">\n'
            '        SELECT item_id\n'
            '        FROM sample_item\n'
            '        WHERE enabled\n'
            '        <if test="codes != null">\n'
            '            AND item_code in\n'
            '            <foreach collection="codes" item="code" open="(" close=")" separator=",">\n'
            '                #{code}\n'
            '            </foreach>\n'
            '        </if>\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace('item_code in', 'item_code IN')
        config = Config()
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-mybatis-sql", "IR-keyword-case"]
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_keeps_case_edits_when_layout_is_rejected(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT\n'
            '            <include refid="External.Columns1" />,\n'
            '            <include refid="External.Columns2" />,\n'
            '            <include refid="External.Columns3" />,\n'
            '            <include refid="External.Columns4" />,\n'
            '            <include refid="External.Columns5" />,\n'
            '        source.source_type_id::text as source_type_id,\n'
            '        st_asgeojson(st_makepoint(item.longitude, item.latitude)) as boundary\n'
            '        FROM sample.item item\n'
            '        LEFT JOIN sample.extra extra\n'
            '        ON item.id = extra.id\n'
            '        LEFT JOIN sample.item_keyword ik\n'
            '        ON item.id = ik.item_id\n'
            '        LEFT JOIN sample.keyword keyword\n'
            '        ON ik.keyword_id = keyword.id\n'
            '        LEFT JOIN sample.item_media im\n'
            '        ON item.id = im.item_id\n'
            '        LEFT JOIN sample.media media\n'
            '        ON im.media_id = media.id\n'
            '        LEFT JOIN sample.source source\n'
            '        ON item.source_id = source.id\n'
            '        LEFT JOIN sample.source_role sr\n'
            '        ON source.id = sr.source_id\n'
            '        LEFT JOIN sample.user_role ur\n'
            '        ON ur.role_name = sr.role_name\n'
            '        LEFT JOIN sample.user_account account\n'
            '        ON account.id = ur.user_id\n'
            '        WHERE\n'
            '            <if test="start != null and end != null">\n'
            "                item.created_at BETWEEN timezone('utc', '${start}') AND timezone('utc', '${end}') AND\n"
            '            </if>\n'
            "            <if test=\"start != null and end == null\">item.created_at &gt;= timezone('utc', '${start}') AND</if>\n"
            "            <if test=\"start == null and end != null\">item.created_at &lt;= timezone('utc', '${end}') AND</if>\n"
            '            <if test="source != null">source.source_type_id = #{source} AND</if>\n'
            '            <if test="userId != null">(account.id = ${userId} OR sr.role_name IS NULL) AND</if>\n'
            '        keyword.active\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertIn(
            'source.source_type_id::TEXT AS source_type_id',
            first.content,
        )
        self.assertIn('st_makepoint(item.longitude, item.latitude)) AS boundary', first.content)
        self.assertEqual(second.content, first.content)

    def test_xml_mybatis_maps_function_case_inside_dynamic_foreach(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <insert id="insertShapes">\n'
            '        INSERT INTO sample_shape (shape)\n'
            '        SELECT st_union(\n'
            '            <foreach collection="shapes" item="shape">\n'
            '                ST_geomfromgeojson(#{shape})\n'
            '            </foreach>\n'
            '        )\n'
            '    </insert>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            'ST_geomfromgeojson',
            'st_geomfromgeojson',
        )
        config = Config()
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-mybatis-sql", "IR-function-case"]
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_indents_dynamic_projection_without_from(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <insert id="insertShapes">\n'
            '        INSERT INTO sample_shape (owner_id, shape)\n'
            '        (\n'
            '            SELECT\n'
            '            #{ownerId},\n'
            '            st_union(\n'
            '                <foreach collection="shapes" item="shape">\n'
            '                    st_geomfromgeojson(#{shape})\n'
            '                </foreach>\n'
            '            )\n'
            '        )\n'
            '    </insert>\n'
            '</mapper>'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <insert id="insertShapes">\n'
            '        INSERT INTO sample_shape (owner_id, shape)\n'
            '        (\n'
            '            SELECT\n'
            '                #{ownerId},\n'
            '                st_union(\n'
            '                    <foreach collection="shapes" item="shape">\n'
            '                        st_geomfromgeojson(#{shape})\n'
            '                    </foreach>\n'
            '                )\n'
            '        )\n'
            '    </insert>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")
        check_config = Config()
        check_config.profile = "commit"
        checked = process_document(
            check_config,
            second.content,
            "generic.xml",
            "xml",
        )

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)
        self.assertFalse(checked.diagnostics)

    def test_xml_indent_preserves_between_continuation_in_dynamic_where(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="activeItems">\n'
            '        SELECT item_id FROM sample_item\n'
            '        <if test="start != null and end != null">\n'
            '            WHERE\n'
            '            recorded_at BETWEEN #{start}\n'
            '                AND #{end}\n'
            '                OR (completed_at BETWEEN #{start} AND #{end})\n'
            '        </if>\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-indent"]
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, xml_content)
        self.assertEqual(second.content, xml_content)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_case_boolean_continuation_indent(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="categorizedItems">\n'
            '        SELECT\n'
            '            CASE\n'
            '                WHEN enabled\n'
            '        AND ready\n'
            "                    THEN 'ready'\n"
            "                ELSE 'waiting'\n"
            '            END AS status\n'
            '        FROM sample_item\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            '        AND ready',
            '                    AND ready',
        )
        config = Config()
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-indent"]
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_dynamic_join_modifier_starts_join_line(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="joinedItems">\n'
            '        SELECT item.item_id\n'
            '        FROM\n'
            '            sample_item item\n'
            '            <if test="includeMissing">LEFT</if> JOIN sample_owner entity_alias USING (owner_id)\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            '</if> JOIN sample_owner',
            '</if>\n            JOIN sample_owner',
        )
        config = Config()
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_compacts_short_static_order_by(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="orderedItems">\n'
            '        SELECT item_id\n'
            '        FROM sample_item\n'
            '        ORDER BY\n'
            '            item_name,\n'
            '            recorded_at\n'
            '    </select>\n'
            '</mapper>'
        )
        expected = xml_content.replace(
            'ORDER BY\n            item_name,\n            recorded_at',
            'ORDER BY item_name, recorded_at',
        )
        config = Config()
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

        inline_in_branch = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="orderedItems">\n'
            '        <choose>\n'
            '            <when test="byName">\n'
            '                SELECT item_id\n'
            '                FROM sample_item\n'
            '                order By item_name, recorded_at\n'
            '            </when>\n'
            '            <otherwise>SELECT item_id FROM sample_item</otherwise>\n'
            '        </choose>\n'
            '    </sql>\n'
            '</mapper>'
        )
        branch_first = process_document(
            config, inline_in_branch, "generic.xml", "xml"
        )
        branch_second = process_document(
            config, branch_first.content, "generic.xml", "xml"
        )
        self.assertIn(
            '                ORDER BY item_name, recorded_at\n',
            branch_first.content,
        )
        self.assertEqual(branch_second.content, branch_first.content)
        self.assertFalse(branch_first.diagnostics)

        optional_suffix = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="orderedItems">\n'
            '        SELECT item_id\n'
            '        FROM sample_item\n'
            '        ORDER BY item_name <if test="thenDate">, recorded_at</if>\n'
            '    </select>\n'
            '</mapper>'
        )
        suffix_result = process_document(
            config, optional_suffix, "generic.xml", "xml"
        )
        self.assertIn(
            'ORDER BY item_name <if test="thenDate">',
            suffix_result.content,
        )

    def test_xml_mybatis_preserves_inline_dynamic_single_from(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '            <choose>\n'
            '                <when test="archived">\n'
            '                    SELECT item_id\n'
            '                    FROM\n'
            '                        archived_item item\n'
            '                </when>\n'
            '                <otherwise>\n'
            '                    SELECT item_id\n'
            '                    FROM current_item item\n'
            '                </otherwise>\n'
            '            </choose>\n'
            '            JOIN sample_owner owner ON owner.owner_id = item.owner_id\n'
            '        WHERE owner.enabled\n'
            '        UNION ALL\n'
            '        SELECT archived_item_id\n'
            '        FROM archived_item\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertIn('                    FROM archived_item item\n', first.content)
        self.assertIn('                    FROM current_item item\n', first.content)
        self.assertEqual(second.content, first.content)
        self.assertFalse(first.diagnostics)

        optional_join = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        <if test="archived">\n'
            '            SELECT item.item_id\n'
            '            FROM\n'
            '                archived_item item\n'
            '            <if test="owners">LEFT JOIN sample_owner owner ON owner.owner_id = item.owner_id</if>\n'
            '        </if>\n'
            '    </select>\n'
            '</mapper>'
        )
        joined = process_document(config, optional_join, "generic.xml", "xml")
        self.assertIn(
            '            FROM\n                archived_item item\n',
            joined.content,
        )
        self.assertFalse(joined.diagnostics)

    def test_xml_mybatis_join_addition_uses_full_line_limit(self):
        join_line = (
            "                    JOIN item_window iw ON item.at BETWEEN "
            "iw.start_at AND iw.start_at + '${periodHrs} Hours'::interval"
        )
        self.assertLessEqual(len(join_line), 120)
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="items">\n'
            '        <choose>\n'
            '            <when test="periodHrs &gt; 0">\n'
            '                SELECT items.item_id\n'
            '                FROM\n'
            '                    sample_period periods\n'
            f'{join_line}\n'
            '            </when>\n'
            '            <otherwise>SELECT item_id FROM sample_item</otherwise>\n'
            '        </choose>\n'
            '    </sql>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertIn(join_line, first.content)
        self.assertEqual(second.content, first.content)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_expands_parenthesized_join_condition(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item.item_id\n'
            '        <if test="named">, item.item_name</if>\n'
            '        FROM\n'
            '            sample_item item\n'
            '            JOIN sample_count count ON count.item_id = item.item_id\n'
            '                AND (NOT #{byGroup}\n'
            '                    OR count.group_id = item.group_id)\n'
            '    </select>\n'
            '</mapper>'
        )
        expected_group = (
            '                AND (\n'
            '                    NOT #{byGroup}\n'
            '                    OR count.group_id = item.group_id\n'
            '                )\n'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertIn(expected_group, first.content)
        self.assertEqual(second.content, first.content)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_choose_branches_do_not_extend_join_predicates(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM\n'
            '            <choose>\n'
            '                <when test="county">\n'
            '                    sample_county_item item\n'
            '                    LEFT JOIN sample_owner owner ON owner.owner_id = item.owner_id\n'
            '                </when>\n'
            '                <otherwise>sample_state_item item</otherwise>\n'
            '            </choose>\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, xml_content)
        self.assertEqual(second.content, xml_content)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_from_layout_does_not_cross_choose_boundary(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '        FROM (\n'
            '            <choose>\n'
            '                <when test="county">SELECT item_id, owner_id FROM sample_county_item</when>\n'
            '                <otherwise>SELECT item_id, owner_id FROM sample_state_item</otherwise>\n'
            '            </choose>\n'
            '        ) item\n'
            '        LEFT JOIN sample_owner owner ON owner.owner_id = item.owner_id\n'
            '    </select>\n'
            '</mapper>'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertIn(
            "        LEFT JOIN sample_owner owner ON owner.owner_id = item.owner_id",
            first.content,
        )
        self.assertEqual(second.content, first.content)
        self.assertFalse(first.diagnostics)

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

    def test_xml_multiline_self_closing_marker_aligns_with_opening_tag(self):
        xml_content = (
            '<root>\n'
            '    <child first="one"\n'
            '           second="two"\n'
            '        />\n'
            '</root>\n'
        )
        expected = xml_content.replace('        />', '    />')
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_generated_dynamic_lists_converge_in_one_run(self):
        fields = [
            ("id", "INTEGER"),
            ("code", "VARCHAR"),
            ("name", "VARCHAR"),
            ("region", "VARCHAR"),
            ("status", "VARCHAR"),
            ("created", "TIMESTAMP"),
            ("updated", "TIMESTAMP"),
            ("active", "BOOLEAN"),
            ("latitude", "DOUBLE"),
            ("longitude", "DOUBLE"),
            ("geometry", "OTHER"),
            ("parentId", "INTEGER"),
        ]
        column_tags = "".join(
            f'      <if test="{name} != null">\n        {name},\n      </if>\n'
            for name, _ in fields
        )
        value_tags = "".join(
            f'      <if test="{name} != null">\n'
            f'        #{{{name},jdbcType={kind}}},\n'
            '      </if>\n'
            for name, kind in fields
        )
        set_tags = "".join(
            f'      <if test="record.{name} != null">\n'
            f'        {name} = #{{record.{name},jdbcType={kind}}},\n'
            '      </if>\n'
            for name, kind in fields
        )
        xml_content = (
            '<mapper namespace="example.GeneratedMapper">\n'
            '  <insert id="insertSelective">\n'
            '    insert into sample_item\n'
            '    <trim prefix="(" suffix=")" suffixOverrides=",">\n'
            + column_tags
            + '    </trim>\n'
            '    <trim prefix="values (" suffix=")" suffixOverrides=",">\n'
            + value_tags
            + '    </trim>\n'
            '  </insert>\n'
            '  <update id="updateSelective">\n'
            '    update sample_item\n'
            '    <set>\n'
            + set_tags
            + '    </set>\n'
            '  </update>\n'
            '</mapper>\n'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, second.content)
        self.assertFalse(
            any("Formatter did not converge" in item for item in first.diagnostics)
        )
        self.assertNotIn("IR-xml-indent", [item[0].rule_id for item in first.violations])

    def test_xml_mybatis_fragment_anchors_its_first_clause_to_the_tag(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="itemSource">\n'
            '              FROM sample_item item\n'
            '         LEFT JOIN sample_owner owner\n'
            '                ON owner.id = item.owner_id\n'
            '        <if test="activeOnly">\n'
            '            WHERE item.active\n'
            '        </if>\n'
            '    </sql>\n'
            '</mapper>\n'
        )
        expected = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="itemSource">\n'
            '        FROM\n'
            '            sample_item item\n'
            '            LEFT JOIN sample_owner owner ON owner.id = item.owner_id\n'
            '            <if test="activeOnly">WHERE item.active</if>\n'
            '    </sql>\n'
            '</mapper>\n'
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_empty_fragment_does_not_shift_safety_signatures(self):
        xml_content = (
            '<mapper namespace="GenericMapper">\n'
            '    <sql id="emptySource">\n'
            '    </sql>\n'
            '    <select id="items">\n'
            '        select item_id from sample_item\n'
            '    </select>\n'
            '</mapper>\n'
        )
        expected = xml_content.replace(
            "        select item_id from sample_item",
            "        SELECT item_id FROM sample_item",
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        first = process_document(config, xml_content, "generic.xml", "xml")
        second = process_document(config, first.content, "generic.xml", "xml")

        self.assertEqual(first.content, expected)
        self.assertEqual(second.content, expected)
        self.assertFalse(first.diagnostics)

    def test_xml_mybatis_foreach_continuation_indentation(self):
        xml_content = (
            '<mapper namespace="MyMapper">\n'
            '    <select id="continued">\n'
            '        SELECT id\n'
            '        FROM users\n'
            '        WHERE\n'
            '            active = true\n'
            '            <if test="ids != null">\n'
            '                AND id IN\n'
            '                <foreach collection="someVeryLongCollectionNameThatKeepsTheForeachBodyOnSeparateLines" item="id" open="(" close=")" separator=",">\n'
            '                        #{id}\n'
            '                </foreach>\n'
            '            </if>\n'
            '    </select>\n'
            '    <select id="standalone">\n'
            '        SELECT id\n'
            '        FROM users\n'
            '        <if test="ids != null">\n'
            '                    <foreach collection="ids" item="id" open="(" close=")" separator=",">#{id}</foreach>\n'
            '        </if>\n'
            '    </select>\n'
            '</mapper>'
        )
        path = self.write_temp_file("test_mybatis_foreach_indent.xml", xml_content)

        config = Config()
        config.paths = [path]
        config.disable_all = True
        config.rules_to_enable = ["IR-xml-indent"]
        config.fix = True

        self.assertEqual(run_linter(config), 0)
        with open(path, "r") as f:
            expected = (
                '<mapper namespace="MyMapper">\n'
                '    <select id="continued">\n'
                '        SELECT id\n'
                '        FROM users\n'
                '        WHERE\n'
                '            active = true\n'
                '            <if test="ids != null">\n'
                '                AND id IN\n'
                '                    <foreach collection="someVeryLongCollectionNameThatKeepsTheForeachBodyOnSeparateLines" item="id" open="(" close=")" separator=",">\n'
                '                        #{id}\n'
                '                    </foreach>\n'
                '            </if>\n'
                '    </select>\n'
                '    <select id="standalone">\n'
                '        SELECT id\n'
                '        FROM users\n'
                '        <if test="ids != null">\n'
                '            <foreach collection="ids" item="id" open="(" close=")" separator=",">#{id}</foreach>\n'
                '        </if>\n'
                '    </select>\n'
                '</mapper>'
            )
            self.assertEqual(f.read(), expected)

        self.assertEqual(run_linter(config), 0)

    def test_xml_mybatis_formats_dynamic_where_and_table_function(self):
        xml_content = (
            '<mapper namespace="MyMapper">\n'
            '    <select id="features">\n'
            '        SELECT feature_id\n'
            '        FROM\n'
            '            outage_data.state_outages_for_run_start_time(#{runStartTime}::TIMESTAMPTZ - INTERVAL \'15 minute\') sofrst\n'
            '               WHERE st_intersects(sofrst.geom, st_geomfromgeojson(#{geomStr}))\n'
            '                <if test="stateAbbreviations != null">\n'
            '                AND sofrst.state_abbreviation IN <foreach collection="stateAbbreviations"  item="abbr" open="(" close=")" separator=",">#{abbr}</foreach>\n'
            '                </if>\n'
            '    </select>\n'
            '</mapper>'
        )
        path = self.write_temp_file("test_mybatis_dynamic_where.xml", xml_content)

        config = Config()
        config.paths = [path]
        config.profile = "commit"
        config.lines = [3]
        config.fix = True

        self.assertEqual(run_linter(config), 0)
        with open(path, "r") as f:
            expected = (
                '<mapper namespace="MyMapper">\n'
                '    <select id="features">\n'
                '        SELECT feature_id\n'
                '        FROM outage_data.state_outages_for_run_start_time(\n'
                '            #{runStartTime}::TIMESTAMP WITH TIME ZONE - INTERVAL \'15 minute\'\n'
                '        ) sofrst\n'
                '        WHERE\n'
                '            st_intersects(sofrst.geom, st_geomfromgeojson(#{geomStr}))\n'
                '            <if test="stateAbbreviations != null">\n'
                '                AND sofrst.state_abbreviation IN\n'
                '                    <foreach collection="stateAbbreviations"  item="abbr" open="(" close=")" separator=",">\n'
                '                        #{abbr}\n'
                '                    </foreach>\n'
                '            </if>\n'
                '    </select>\n'
                '</mapper>'
            )
            self.assertEqual(f.read(), expected)

        self.assertEqual(run_linter(config), 0)

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
