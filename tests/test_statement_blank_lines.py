import unittest
from mir.rules.sql.statement_blank_lines import StatementBlankLinesRule

class TestStatementBlankLines(unittest.TestCase):
    def setUp(self):
        self.rule = StatementBlankLinesRule()

    def test_no_violations(self):
        content = "SELECT 1;\n\nSELECT 2;"
        violations = self.rule.check(content, "test.sql", {})
        self.assertEqual(len(violations), 0)

    def test_violations_same_line(self):
        content = "SELECT 1; SELECT 2;"
        violations = self.rule.check(content, "test.sql", {})
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].line_number, 1)
        
        fixed = self.rule.fix(content, "test.sql", {})
        self.assertEqual(fixed, "SELECT 1;\n\n SELECT 2;")

    def test_violations_next_line(self):
        content = "SELECT 1;\nSELECT 2;"
        violations = self.rule.check(content, "test.sql", {})
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].line_number, 1)
        
        fixed = self.rule.fix(content, "test.sql", {})
        self.assertEqual(fixed, "SELECT 1;\n\nSELECT 2;")

    def test_with_comments_same_line(self):
        content = "SELECT 1; -- comment\nSELECT 2;"
        violations = self.rule.check(content, "test.sql", {})
        self.assertEqual(len(violations), 1)
        
        fixed = self.rule.fix(content, "test.sql", {})
        self.assertEqual(fixed, "SELECT 1; -- comment\n\nSELECT 2;")

    def test_with_comments_next_line(self):
        content = "SELECT 1;\n-- comment for 2\nSELECT 2;"
        violations = self.rule.check(content, "test.sql", {})
        self.assertEqual(len(violations), 1)
        
        fixed = self.rule.fix(content, "test.sql", {})
        self.assertEqual(fixed, "SELECT 1;\n\n-- comment for 2\nSELECT 2;")

if __name__ == "__main__":
    unittest.main()
