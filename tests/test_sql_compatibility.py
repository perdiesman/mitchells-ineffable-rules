import unittest

from mir.rules.sql.paren_content_indent import ParenContentIndentRule
from mir.rules.sql.function_case import FunctionCaseRule
from mir.rules.sql.keyword_case import KeywordCaseRule
from mir.rules.sql.operator_spacing import OperatorSpacingRule
from mir.rules.sql.sql_utils import _tokenize_sql_impl, protected_sql_signature, tokenize_sql
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

    def test_token_cache_is_bounded_across_many_documents(self):
        _tokenize_sql_impl.cache_clear()
        for index in range(80):
            tokenize_sql(f"SELECT {index} AS item_id;")

        self.assertLessEqual(_tokenize_sql_impl.cache_info().currsize, 32)

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

    def test_keyword_function_ambiguity_converges(self):
        content = "select left(item_name, 2) from sample_table left join labels on true;"
        keyword_fixed = KeywordCaseRule().fix(content, "generic.sql", {})
        fixed = FunctionCaseRule().fix(keyword_fixed, "generic.sql", {})

        self.assertEqual(
            fixed,
            "SELECT left(item_name, 2) FROM sample_table LEFT JOIN labels ON true;",
        )
        self.assertEqual(KeywordCaseRule().fix(fixed, "generic.sql", {}), fixed)

    def test_lateral_is_a_keyword_not_a_function(self):
        content = "select item_id from sample_table left join lateral (select 1) item on true;"
        keyword_fixed = KeywordCaseRule().fix(content, "generic.sql", {})
        fixed = FunctionCaseRule().fix(keyword_fixed, "generic.sql", {})

        self.assertIn("LEFT JOIN LATERAL (SELECT 1)", fixed)
        self.assertEqual(FunctionCaseRule().fix(fixed, "generic.sql", {}), fixed)

    def test_set_row_assignment_is_not_a_function(self):
        content = "UPDATE sample_table SET (item_name) = ('example');"

        self.assertEqual(FunctionCaseRule().fix(content, "generic.sql", {}), content)

    def test_postgresql_ddl_keywords_are_not_functions(self):
        content = (
            "CREATE TABLE sample_table (item_id INTEGER, PRIMARY KEY (item_id), "
            "UNIQUE (item_id), CHECK (item_id > 0)); "
            "CREATE TYPE sample_state AS ENUM ('ready'); "
            "CREATE INDEX sample_idx ON sample_table USING GIST (item_id) INCLUDE (item_id);"
        )

        self.assertEqual(FunctionCaseRule().fix(content, "generic.sql", {}), content)

    def test_overlaps_predicate_is_not_a_function(self):
        content = "SELECT (start_at, end_at) OVERLAPS (:start, :end);"

        self.assertEqual(FunctionCaseRule().fix(content, "generic.sql", {}), content)

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

    def test_protected_signature_allows_formatting_inside_dollar_quoted_code(self):
        original = "CREATE FUNCTION sample() RETURNS void AS $$ BEGIN RETURN; END; $$ LANGUAGE plpgsql;"
        formatted = "CREATE FUNCTION sample() RETURNS void AS $$ BEGIN\n    RETURN;\nEND; $$ LANGUAGE plpgsql;"

        self.assertEqual(protected_sql_signature(original), protected_sql_signature(formatted))

    def test_protected_signature_includes_cast_targets(self):
        original = "SELECT :county_fips::text[], CAST(:start AS timestamp with time zone);"
        changed = "SELECT :county_fips::TEXT[], CAST(:start AS TIMESTAMP WITH TIME ZONE);"

        self.assertNotEqual(
            protected_sql_signature(original), protected_sql_signature(changed)
        )

        custom_original = "SELECT payload::archive.custom_type[], CAST(payload AS archive.custom_type[]);"
        custom_changed = "SELECT payload::archive.other_type[], CAST(payload AS archive.other_type[]);"
        self.assertNotEqual(
            protected_sql_signature(custom_original),
            protected_sql_signature(custom_changed),
        )

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
