import unittest

from mir.rules.sql.paren_content_indent import ParenContentIndentRule
from mir.rules.sql.function_case import FunctionCaseRule
from mir.rules.sql.keyword_case import KeywordCaseRule
from mir.rules.sql.operator_spacing import OperatorSpacingRule
from mir.rules.sql.sql_utils import protected_sql_signature, tokenize_sql
from mir.rules.sql.unresolved_alias import UnresolvedAliasRule


class TestSqlCompatibility(unittest.TestCase):
    def test_template_parameters_are_opaque_tokens(self):
        content = (
            "SELECT item_id FROM ${schemaName}.sample_table "
            "WHERE item_id = #{item.id} AND item_name = :filter.name "
            "AND created_at::date = :created_on;"
        )

        tokens = tokenize_sql(content)
        parameters = [token["value"] for token in tokens if token["type"] == "PARAM"]

        self.assertEqual(
            parameters,
            ["${schemaName}", "#{item.id}", ":filter.name", ":created_on"],
        )
        self.assertIn("::", [token["value"] for token in tokens if token["type"] == "CAST"])

    def test_keyword_case_preserves_mybatis_and_trellis_parameters(self):
        content = "select :end, #{limit}, ${order} from sample_table;"
        fixed = KeywordCaseRule().fix(content, "generic.sql", {})

        self.assertEqual(fixed, "SELECT :end, #{limit}, ${order} FROM sample_table;")

    def test_postgresql_contextual_keywords_are_not_functions(self):
        content = (
            "SELECT COUNT(*) FILTER (WHERE enabled) FROM sample_table "
            "ON CONFLICT (item_id) DO UPDATE SET value = excluded.value;"
        )
        fixed = FunctionCaseRule().fix(content, "generic.sql", {})

        self.assertEqual(
            fixed,
            "SELECT count(*) FILTER (WHERE enabled) FROM sample_table "
            "ON CONFLICT (item_id) DO UPDATE SET value = excluded.value;",
        )

    def test_postgresql_operators_remain_atomic_when_spaced(self):
        content = (
            "SELECT row_data->>'key', row_data#>>'{path}', sample_table.* "
            "FROM sample_table WHERE days=>:days;"
        )
        fixed = OperatorSpacingRule().fix(content, "generic.sql", {})

        self.assertEqual(
            fixed,
            "SELECT row_data ->> 'key', row_data #>> '{path}', sample_table.* "
            "FROM sample_table WHERE days => :days;",
        )
        self.assertEqual(protected_sql_signature(fixed), protected_sql_signature(content))

    def test_foreign_schema_limit_list_is_not_a_function_call(self):
        content = (
            "IMPORT FOREIGN SCHEMA sample_remote LIMIT TO (sample_table) "
            "FROM SERVER sample_server INTO sample_local;"
        )

        rule = ParenContentIndentRule()
        self.assertEqual(rule.check(content, "generic.sql", {}), [])
        self.assertEqual(rule.fix(content, "generic.sql", {}), content)

    def test_postgresql_excluded_relation_is_resolved(self):
        content = (
            "INSERT INTO sample_table (item_id, item_value) VALUES (1, 'x') "
            "ON CONFLICT (item_id) DO UPDATE SET item_value = excluded.item_value;"
        )

        rule = UnresolvedAliasRule()
        self.assertEqual(rule.check(content, "generic.sql", {}), [])

    def test_excluded_is_not_globally_treated_as_a_relation(self):
        content = "SELECT excluded.item_value FROM sample_table;"

        violations = UnresolvedAliasRule().check(content, "generic.sql", {})

        self.assertEqual(len(violations), 1)
        self.assertIn("excluded", violations[0].message)


if __name__ == "__main__":
    unittest.main()
