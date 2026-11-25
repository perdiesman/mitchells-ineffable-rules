import unittest

from mir.rules.xml.xml_mybatis_sql import (
    XmlMybatisSqlRule,
    get_all_elements_recursively,
    get_mybatis_protected_signatures,
    parse_xml_elements,
)
from mir.rules.xml.xml_utils import tokenize_xml


class TestXmlMybatisParser(unittest.TestCase):
    def test_foreach_projection_preserves_parameter_options(self):
        source = """<mapper namespace="sample.Mapper">
    <insert id="startHistory">
        <foreach collection="items" item="item">
            INSERT INTO sample_history (item_id, threshold)
            SELECT
                #{item.id},
                #{item.threshold,jdbcType=INTEGER}
            FROM sample_item;
        </foreach>
    </insert>
</mapper>"""
        expected = source.replace(
            "SELECT\n                #{item.id},\n                #{item.threshold,jdbcType=INTEGER}",
            "SELECT #{item.id}, #{item.threshold,jdbcType=INTEGER}",
        )
        rule = XmlMybatisSqlRule()
        config = {"_profile": "commit"}

        fixed = rule.fix(source, "generic.xml", config)

        self.assertEqual(fixed, expected)
        self.assertEqual(
            get_mybatis_protected_signatures(fixed),
            get_mybatis_protected_signatures(source),
        )
        self.assertEqual(rule.check(fixed, "generic.xml", config), [])
        self.assertEqual(rule.fix(fixed, "generic.xml", config), fixed)

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

    def test_protected_signatures_can_target_one_statement(self):
        content = """<mapper namespace="sample.Mapper">
    <sql id="columns">item_id, item_name</sql>
    <select id="findItems">SELECT <include refid="columns" /> FROM sample_item</select>
    <select id="findOther">SELECT other_id FROM other_item</select>
</mapper>"""

        all_signatures = get_mybatis_protected_signatures(content)
        targeted = get_mybatis_protected_signatures(
            content, target=("select", "findItems")
        )

        self.assertEqual(len(all_signatures), 3)
        self.assertEqual(targeted, (all_signatures[1],))


if __name__ == "__main__":
    unittest.main()
