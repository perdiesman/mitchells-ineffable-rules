import unittest

from mir.rules.xml.xml_mybatis_sql import get_all_elements_recursively, parse_xml_elements
from mir.rules.xml.xml_utils import tokenize_xml


class TestXmlMybatisParser(unittest.TestCase):
    def test_nested_elements_keep_document_relative_indexes(self):
        content = """<mapper namespace="sample.Mapper">
    <select id="findItems">
        SELECT item_id
        <if test="activeOnly">
            FROM sample_table
        </if>
    </select>
</mapper>"""
        tokens = tokenize_xml(content)

        elements = get_all_elements_recursively(parse_xml_elements(tokens))
        by_tag = {element["tag"]: element for element in elements}

        self.assertEqual([element["tag"] for element in elements], ["mapper", "select", "if"])
        for element in elements:
            self.assertEqual(tokens[element["start_idx"]]["start"], element["start_offset"])
            self.assertEqual(tokens[element["end_idx"]]["end"], element["end_offset"])
        self.assertIn("FROM sample_table", "".join(t["value"] for t in by_tag["if"]["inner_tokens"]))

    def test_self_closing_children_are_in_document_order(self):
        content = "<mapper><resultMap id=\"sample\"><id column=\"item_id\" /></resultMap></mapper>"

        elements = get_all_elements_recursively(parse_xml_elements(tokenize_xml(content)))

        self.assertEqual([element["tag"] for element in elements], ["mapper", "resultmap", "id"])


if __name__ == "__main__":
    unittest.main()
