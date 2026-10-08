import unittest
from unittest.mock import patch

from mir.engine.embedded_bridge import (
    check_embedded_content,
    fix_embedded_content,
    get_guest_rules,
    is_fixed_text_xml_safe,
)
from mir.engine.rule_interface import BaseRule


class FailingEmbeddedRule(BaseRule):
    rule_id = "IR-test-failing-embedded"
    description = "Test error propagation."
    category = "test"
    is_fixable = "yes"
    embedded_safe = True

    def check(self, content, file_path, rule_config):
        raise RuntimeError("embedded check failed")

    def fix(self, content, file_path, rule_config):
        raise RuntimeError("embedded fix failed")


class TestEmbeddedBridgeSafety(unittest.TestCase):
    @patch("mir.engine.embedded_bridge.get_guest_rules", return_value=[FailingEmbeddedRule()])
    def test_embedded_rule_failures_are_not_silenced(self, _guest_rules):
        with self.assertRaisesRegex(RuntimeError, "embedded check failed"):
            check_embedded_content("sql", "SELECT 1", list(range(8)), "generic.xml", {})
        with self.assertRaisesRegex(RuntimeError, "embedded fix failed"):
            fix_embedded_content("sql", "SELECT 1", list(range(8)), "generic.xml", {})

    def test_mybatis_guest_rules_are_selected_by_metadata(self):
        rules = get_guest_rules("sql", {}, require_embedded_safe=True)
        rule_ids = {rule.rule_id for rule in rules}

        self.assertIn("IR-keyword-case", rule_ids)
        self.assertIn("IR-clause-alignment", rule_ids)
        self.assertNotIn("IR-paren-content-indent", rule_ids)
        self.assertNotIn("IR-trellis-directives", rule_ids)
        self.assertTrue(all(rule.embedded_safe for rule in rules))

    def test_text_edits_may_change_sql_structure(self):
        content = "<select>select (item_id) from sample_table</select>"
        tag_ranges = [(0, 8), (42, 51)]

        self.assertTrue(
            is_fixed_text_xml_safe(content, tag_ranges, [(8, 42, "SELECT item_id FROM sample_table")])
        )

    def test_edit_intersecting_tag_is_rejected(self):
        content = "<select>SELECT item_id</select>"
        tag_ranges = [(0, 8), (22, 31)]

        self.assertFalse(is_fixed_text_xml_safe(content, tag_ranges, [(1, 7, "update")]))

    def test_insertion_inside_tag_is_rejected_but_boundaries_are_safe(self):
        content = "<select>SELECT item_id</select>"
        tag_ranges = [(0, 8), (22, 31)]

        self.assertFalse(is_fixed_text_xml_safe(content, tag_ranges, [(4, 4, "x")]))
        self.assertTrue(is_fixed_text_xml_safe(content, tag_ranges, [(8, 8, "\n")]))
        self.assertFalse(is_fixed_text_xml_safe(content, tag_ranges, [(22, 22, "\n")]))

    def test_overlapping_edits_are_rejected(self):
        self.assertFalse(is_fixed_text_xml_safe("plain text", [], [(0, 5, "a"), (4, 6, "b")]))


if __name__ == "__main__":
    unittest.main()
