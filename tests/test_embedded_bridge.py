import unittest

from mir.engine.embedded_bridge import is_fixed_text_xml_safe


class TestEmbeddedBridgeSafety(unittest.TestCase):
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

    def test_overlapping_edits_are_rejected(self):
        self.assertFalse(is_fixed_text_xml_safe("plain text", [], [(0, 5, "a"), (4, 6, "b")]))


if __name__ == "__main__":
    unittest.main()
