import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mir.engine.disabler import get_disabled_rules_map, extract_comments_and_code_lines

class TestDisabler(unittest.TestCase):
    def test_sql_comments_parsing(self):
        content = """SELECT * FROM users;
-- IR-line-length
SELECT * FROM table_with_a_very_long_name_that_exceeds_the_limit_of_characters_on_one_line;
-- IR-start-keyword-case
select * from users;
select * from products;
-- IR-end-keyword-case
select * from orders;
"""
        lines, line_comments, comment_only_lines = extract_comments_and_code_lines(content, "sql")
        self.assertEqual(len(lines), 8)
        self.assertIn(2, line_comments)
        self.assertIn(2, comment_only_lines)
        self.assertIn(4, line_comments)
        self.assertIn(4, comment_only_lines)
        self.assertIn(7, line_comments)
        self.assertIn(7, comment_only_lines)
        
        disabled_map = get_disabled_rules_map(content, "test.sql")
        # Line 3 should have IR-line-length disabled (single line disable on line 2)
        self.assertIn(3, disabled_map.get("IR-line-length", set()))
        self.assertNotIn(4, disabled_map.get("IR-line-length", set()))
        
        # Block disable of IR-keyword-case starts at line 4 (comment on 4, block spans 5, 6)
        keyword_disabled = disabled_map.get("IR-keyword-case", set())
        self.assertIn(5, keyword_disabled)
        self.assertIn(6, keyword_disabled)
        # Ends after line 7 comment, so line 8 is not disabled
        self.assertNotIn(8, keyword_disabled)

    def test_single_line_disable_carries_over_comments(self):
        content = """-- IR-line-length
-- Another comment
-- Yet another comment
SELECT * FROM long_line;
"""
        disabled_map = get_disabled_rules_map(content, "test.sql")
        # The single line disable on line 1 should carry over lines 2 & 3 (comments) to line 4
        self.assertIn(4, disabled_map.get("IR-line-length", set()))

if __name__ == "__main__":
    unittest.main()
