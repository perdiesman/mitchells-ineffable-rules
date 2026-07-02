import os
import sys
import unittest
import tempfile
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mir.engine.rules_loader import load_rules_for_language
from mir.engine.rules_help import get_supported_languages
from mir.engine.runner import find_files

# Dynamic rule content for SQL extension
SQL_EXT_RULE_CONTENT = """
from mir.engine.rule_interface import BaseRule, Violation

class CustomSqlRule(BaseRule):
    rule_id = "IR-custom-sql"
    description = "Custom SQL rule description."
    category = "general"
    is_fixable = "no"

    def check(self, content, file_path, rule_config):
        return []
"""

# Dynamic rule content for Custom language "foo"
FOO_RULE_CONTENT = """
from mir.engine.rule_interface import BaseRule, Violation

class CustomFooRule(BaseRule):
    rule_id = "IR-custom-foo"
    description = "Custom Foo rule description."
    category = "general"
    is_fixable = "no"

    def check(self, content, file_path, rule_config):
        return []
"""

# Dynamic categories mapping for Custom language "foo"
FOO_INIT_CONTENT = """
CATEGORIES = {
    "general": "General Foo Rules",
    "special": "Special Foo Rules"
}
"""

class TestDynamicLoader(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        
    def create_custom_rule(self, lang: str, filename: str, content: str, init_content: str = None) -> str:
        lang_dir = os.path.join(self.temp_dir, lang.lower())
        os.makedirs(lang_dir, exist_ok=True)
        
        if init_content is not None:
            with open(os.path.join(lang_dir, "__init__.py"), "w") as f:
                f.write(init_content)
                
        rule_file = os.path.join(lang_dir, filename)
        with open(rule_file, "w") as f:
            f.write(content)
        return lang_dir

    def test_dynamic_languages_discovery(self):
        # 1. Initially, supported languages should include built-in "sql", "java", "xml"
        initial_langs = get_supported_languages()
        self.assertIn("sql", initial_langs)
        self.assertIn("java", initial_langs)
        self.assertIn("xml", initial_langs)
        self.assertNotIn("foo", initial_langs)
        
        # 2. Add custom language "foo" inside include directory
        self.create_custom_rule("foo", "rule_foo.py", FOO_RULE_CONTENT, FOO_INIT_CONTENT)
        
        # 3. Requesting supported languages passing the include dir
        updated_langs = get_supported_languages([self.temp_dir])
        self.assertIn("sql", updated_langs)
        self.assertIn("java", updated_langs)
        self.assertIn("xml", updated_langs)
        self.assertIn("foo", updated_langs) # Discovered dynamically!

    def test_find_files_dynamic_extensions(self):
        self.create_custom_rule("foo", "rule_foo.py", FOO_RULE_CONTENT, FOO_INIT_CONTENT)
        
        # Create temp files
        t_dir = tempfile.mkdtemp()
        try:
            sql_file = os.path.join(t_dir, "query.sql")
            foo_file = os.path.join(t_dir, "script.foo")
            txt_file = os.path.join(t_dir, "notes.txt")
            
            for f in (sql_file, foo_file, txt_file):
                with open(f, "w") as out:
                    out.write("SELECT 1;")
                    
            # 1. No include dirs -> only finds .sql (not .foo, not .txt)
            files = find_files([t_dir])
            self.assertIn(sql_file, files)
            self.assertNotIn(foo_file, files)
            
            # 2. Passing include dir containing foo language -> finds both .sql and .foo!
            files_with_ext = find_files([t_dir], [self.temp_dir])
            self.assertIn(sql_file, files_with_ext)
            self.assertIn(foo_file, files_with_ext)
            self.assertNotIn(txt_file, files_with_ext)
        finally:
            shutil.rmtree(t_dir)

    def test_load_rules_extend_mode(self):
        # Create a custom rule in "sql" subdirectory of include dir
        self.create_custom_rule("sql", "custom_sql.py", SQL_EXT_RULE_CONTENT)
        
        # Load rules in extend mode (default)
        rules = load_rules_for_language("sql", [self.temp_dir], "extend")
        
        # Should contain both builtin SQL rules and our custom SQL rule
        rule_ids = [r.rule_id for r in rules]
        self.assertIn("IR-line-length", rule_ids)
        self.assertIn("IR-keyword-case", rule_ids)
        self.assertIn("IR-custom-sql", rule_ids)

    def test_load_rules_replace_mode(self):
        # Create a custom rule in "sql" subdirectory of include dir
        self.create_custom_rule("sql", "custom_sql.py", SQL_EXT_RULE_CONTENT)
        
        # Load rules in replace mode
        rules = load_rules_for_language("sql", [self.temp_dir], "replace")
        
        # Should contain ONLY our custom SQL rule, built-ins are replaced/discarded
        rule_ids = [r.rule_id for r in rules]
        self.assertNotIn("IR-line-length", rule_ids)
        self.assertNotIn("IR-keyword-case", rule_ids)
        self.assertIn("IR-custom-sql", rule_ids)

    def test_custom_rule_validation_missing_check(self):
        from mir.engine.rules_loader import RuleValidationError
        
        # Rule that does not implement check method
        invalid_rule_content = """
from mir.engine.rule_interface import BaseRule

class InvalidRule(BaseRule):
    rule_id = "IR-invalid"
    description = "Test missing check."
    category = "general"
    is_fixable = "no"
"""
        self.create_custom_rule("sql", "invalid_sql.py", invalid_rule_content)
        
        with self.assertRaises(RuleValidationError):
            load_rules_for_language("sql", [self.temp_dir], "extend")

    def test_custom_rule_validation_missing_fields(self):
        from mir.engine.rules_loader import RuleValidationError
        
        # Rule with missing attributes
        invalid_rule_content = """
from mir.engine.rule_interface import BaseRule

class InvalidRule(BaseRule):
    rule_id = "IR-invalid"
    # description is missing!
    category = "general"
    is_fixable = "no"
    
    def check(self, content, file_path, rule_config):
        return []
"""
        self.create_custom_rule("sql", "invalid_sql.py", invalid_rule_content)
        
        with self.assertRaises(RuleValidationError):
            load_rules_for_language("sql", [self.temp_dir], "extend")

    def test_custom_rule_validation_syntax_error(self):
        from mir.engine.rules_loader import RuleValidationError
        
        # Rule with syntax error
        invalid_rule_content = """
class InvalidRule
    def check()
"""
        self.create_custom_rule("sql", "invalid_sql.py", invalid_rule_content)
        
        with self.assertRaises(RuleValidationError):
            load_rules_for_language("sql", [self.temp_dir], "extend")

if __name__ == "__main__":
    unittest.main()
