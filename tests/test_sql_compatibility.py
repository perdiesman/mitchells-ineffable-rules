import unittest

from mir.rules.sql.function_case import FunctionCaseRule
from mir.rules.sql.from_multi import FromMultiRule
from mir.rules.sql.clause_alignment import ClauseAlignmentRule
from mir.rules.sql.case_when_wrap import CaseWhenWrapRule
from mir.rules.sql.column_layout import ColumnLayoutRule
from mir.rules.sql.comma_style import CommaStyleRule
from mir.rules.sql.join_on_multi import JoinOnMultiRule
from mir.rules.sql.keyword_case import KeywordCaseRule
from mir.rules.sql.line_length import LineLengthRule
from mir.rules.sql.named_parameters import NamedParametersRule
from mir.rules.sql.operator_spacing import OperatorSpacingRule
from mir.rules.sql.paren_content_indent import ParenContentIndentRule
from mir.rules.sql.paren_multi import ParenMultiRule
from mir.rules.sql.paren_same_op import ParenSameOpRule
from mir.rules.sql.paren_single import ParenSingleRule
from mir.rules.sql.parenthesized_expression_wrap import ParenthesizedExpressionWrapRule
from mir.rules.sql.sql_utils import _tokenize_sql_impl, protected_sql_signature, tokenize_sql
from mir.rules.sql.statement_semicolon import StatementSemicolonRule
from mir.rules.sql.subquery_indent import SubqueryIndentRule
from mir.rules.sql.trailing_semicolon import TrailingSemicolonRule
from mir.rules.sql.unresolved_alias import UnresolvedAliasRule
from mir.rules.sql.where_multi import WhereMultiRule


class TestSqlCompatibility(unittest.TestCase):
    def test_parenthesized_ratio_wrap_is_exact_and_idempotent(self):
        source = (
            "    (coalesce(max(current_outage), 0)::NUMERIC / "
            "greatest(coalesce(sum(normal_value * county_percent), 1)::INTEGER, 1)) "
            "- 1 AS outage_count"
        )
        expected = (
            "    (\n"
            "        coalesce(max(current_outage), 0)::NUMERIC\n"
            "        / greatest(\n"
            "            coalesce(\n"
            "                sum(normal_value * county_percent),\n"
            "                1\n"
            "            )::INTEGER,\n"
            "            1\n"
            "        )\n"
            "    ) - 1 AS outage_count"
        )
        rule = ParenthesizedExpressionWrapRule()

        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), expected)
        self.assertEqual(rule.check(fixed, "generic.sql", {}), [])

    def test_short_where_compacts_independently_of_the_previous_from_line(self):
        source = (
            "FROM outage_data.materialized_zip_additional_information\n"
            "WHERE\n"
            "    :states = 'All'\n"
            "    OR state_abbreviation = ANY(:states)"
        )
        expected = (
            "FROM outage_data.materialized_zip_additional_information\n"
            "WHERE :states = 'All' OR state_abbreviation = ANY(:states)"
        )

        rule = WhereMultiRule()
        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.check(fixed, "generic.sql", {}), [])

    def test_medium_where_wraps_after_a_long_from_line(self):
        source = (
            "FROM notification.vw_additional_timeslider_events\n"
            "WHERE timeslider_event_type = :type AND timeslider_event_created_at "
            "BETWEEN :start_date AND :end_date"
        )
        expected = (
            "FROM notification.vw_additional_timeslider_events\n"
            "WHERE\n"
            "    timeslider_event_type = :type\n"
            "    AND timeslider_event_created_at BETWEEN :start_date AND :end_date"
        )

        rule = WhereMultiRule()
        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)

    def test_case_arm_stays_inline_within_its_line_length_limit(self):
        source = (
            "                        WHEN u.active AND coalesce(su.active, true) "
            "THEN coalesce(ucc.collected_count, 0)"
        )

        self.assertEqual(CaseWhenWrapRule().fix(source, "generic.sql", {}), source)

    def test_long_case_condition_aligns_root_boolean_and_then(self):
        source = (
            "                WHEN TRUE = ANY(SELECT unnest(collected_counts) IS NULL) "
            "AND array_length(collected_counts, 1) > 1 THEN 'mixed'"
        )
        expected = (
            "                WHEN TRUE = ANY(SELECT unnest(collected_counts) IS NULL)\n"
            "                    AND array_length(collected_counts, 1) > 1\n"
            "                    THEN 'mixed'"
        )

        self.assertEqual(CaseWhenWrapRule().fix(source, "generic.sql", {}), expected)

    def test_long_case_result_does_not_split_a_short_boolean_condition(self):
        source = (
            "                    WHEN u.active AND coalesce(su.active, true) "
            "THEN coalesce(ucc.collected_count, ucc.model_count, 0)"
        )
        expected = (
            "                    WHEN u.active AND coalesce(su.active, true)\n"
            "                        THEN coalesce(ucc.collected_count, ucc.model_count, 0)"
        )

        self.assertEqual(CaseWhenWrapRule().fix(source, "generic.sql", {}), expected)

    def test_line_length_expands_the_last_call_in_a_filter_expression(self):
        source = (
            "            count(*) FILTER (WHERE current_date = run_start_date "
            "AND (needs_running OR is_running)) >= 1 AS calculating_today"
        )
        expected = (
            "            count(*) FILTER (\n"
            "                WHERE current_date = run_start_date AND (needs_running OR is_running)\n"
            "            ) >= 1 AS calculating_today"
        )

        self.assertEqual(
            LineLengthRule().fix(source, "generic.sql", {"max_length": 100}),
            expected,
        )

    def test_join_wraps_before_on_when_the_predicate_fits_its_own_line(self):
        source = (
            "                LEFT JOIN outage_data.running_calculation_handlers rch_cuh "
            "ON rch_cuh.handler_id = county_utility_handler"
        )
        expected = (
            "                LEFT JOIN outage_data.running_calculation_handlers rch_cuh\n"
            "                    ON rch_cuh.handler_id = county_utility_handler"
        )

        rule = JoinOnMultiRule()
        fixed = rule.fix(source, "generic.sql", {"max_line_length": 100})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.check(fixed, "generic.sql", {"max_line_length": 100}), [])

    def test_join_wraps_after_operator_when_the_left_side_still_fits(self):
        source = (
            "    JOIN outage_data.outage_summary_error_type oset ON oset.id = "
            "outage_summary_error.outage_summary_error_type_id"
        )
        expected = (
            "    JOIN outage_data.outage_summary_error_type oset ON oset.id =\n"
            "        outage_summary_error.outage_summary_error_type_id"
        )

        rule = JoinOnMultiRule()
        fixed = rule.fix(source, "generic.sql", {"max_line_length": 100})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.check(fixed, "generic.sql", {"max_line_length": 100}), [])

    def test_long_join_between_wraps_only_the_range_delimiter(self):
        source = (
            "    JOIN sample_override override ON override.item_id = item.id\n"
            "        AND override.recorded_at BETWEEN :long_interval_start_value "
            "AND :long_interval_end_value"
        )
        expected = (
            "    JOIN sample_override override ON override.item_id = item.id\n"
            "        AND override.recorded_at BETWEEN :long_interval_start_value\n"
            "            AND :long_interval_end_value"
        )

        rule = JoinOnMultiRule()
        fixed = rule.fix(source, "generic.sql", {"max_line_length": 80})

        self.assertEqual(fixed, expected)

    def test_line_length_compacts_a_simple_call_when_expression_fits(self):
        source = (
            "    (sum(\n"
            "        outage_count\n"
            "    ) * county_percent)::INTEGER AS override_count"
        )
        expected = "    (sum(outage_count) * county_percent)::INTEGER AS override_count"

        self.assertEqual(
            LineLengthRule().fix(source, "generic.sql", {"max_length": 100}),
            expected,
        )

    def test_comma_style_removes_space_before_trailing_comma(self):
        source = "SELECT coalesce(item_count::NUMERIC , 0::NUMERIC) FROM sample_item;"
        expected = "SELECT coalesce(item_count::NUMERIC, 0::NUMERIC) FROM sample_item;"

        rule = CommaStyleRule()

        self.assertEqual(rule.fix(source, "generic.sql", {}), expected)
        self.assertEqual(rule.check(expected, "generic.sql", {}), [])

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

    def test_keyword_case_handles_overlapping_configured_phrases(self):
        content = "select item_id group by item_id order by item_id;"
        fixed = KeywordCaseRule().fix(
            content,
            "generic.sql",
            {"additional_keywords": ["group", "group by", "order by"]},
        )

        self.assertEqual(fixed, "SELECT item_id GROUP BY item_id ORDER BY item_id;")

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

    def test_compound_join_type_stays_on_one_line(self):
        content = (
            "SELECT first_table.item_id FROM first_table FULL\n"
            "    OUTER JOIN second_table ON first_table.item_id = second_table.item_id;"
        )
        expected = (
            "SELECT first_table.item_id FROM\n"
            "    first_table\n"
            "    FULL OUTER JOIN second_table ON first_table.item_id = second_table.item_id;"
        )

        rule = FromMultiRule()
        fixed = rule.fix(content, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.check(fixed, "generic.sql", {}), [])
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), fixed)

    def test_natural_compound_join_type_stays_on_one_line(self):
        content = "SELECT * FROM first_table NATURAL FULL OUTER JOIN second_table;"
        expected = (
            "SELECT * FROM\n"
            "    first_table\n"
            "    NATURAL FULL OUTER JOIN second_table;"
        )

        self.assertEqual(FromMultiRule().fix(content, "generic.sql", {}), expected)

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

    def test_distinct_on_is_not_a_join_condition(self):
        content = (
            "SELECT DISTINCT ON (record.item_id) record.item_id\n"
            "FROM sample_record record\n"
            "JOIN sample_state state ON state.id = record.state_id;"
        )

        self.assertEqual(JoinOnMultiRule().check(content, "generic.sql", {}), [])

    def test_is_not_distinct_from_is_not_a_from_clause(self):
        content = (
            "SELECT item.item_id\nFROM sample_item item\n"
            "WHERE item.parent_id IS NOT DISTINCT FROM :parent_id;"
        )

        self.assertEqual(ClauseAlignmentRule().check(content, "generic.sql", {}), [])

    def test_is_distinct_from_is_not_a_from_clause(self):
        content = (
            "SELECT item.item_id\nFROM sample_item item\n"
            "WHERE (item.state, item.value) IS DISTINCT FROM (:state, :value);"
        )

        self.assertEqual(ClauseAlignmentRule().check(content, "generic.sql", {}), [])

    def test_clause_alignment_ignores_dollar_quoted_function_body(self):
        content = (
            "CREATE FUNCTION sample_function() RETURNS void AS $body$\n"
            "select item_id from sample_item where active;\n"
            "$body$ LANGUAGE sql;"
        )

        self.assertEqual(ClauseAlignmentRule().fix(content, "generic.sql", {}), content)

    def test_clause_alignment_keeps_statements_independent(self):
        content = (
            "SELECT item_id\nFROM sample_item;\n"
            "    SELECT state_id\n    FROM sample_state;"
        )

        self.assertEqual(ClauseAlignmentRule().fix(content, "generic.sql", {}), content)

    def test_cte_and_lateral_parentheses_are_not_function_calls(self):
        content = (
            "WITH sample_rows AS (SELECT item_id FROM sample_item)\n"
            "SELECT lateral_rows.item_id\nFROM sample_rows\n"
            "LEFT JOIN LATERAL (SELECT item_id FROM sample_item) lateral_rows ON true;"
        )

        self.assertEqual(NamedParametersRule().check(content, "generic.sql", {}), [])
        self.assertEqual(UnresolvedAliasRule().check(content, "generic.sql", {}), [])

    def test_postgresql_predicate_parentheses_are_preserved(self):
        content = (
            "SELECT max(item.value) FILTER (WHERE item.enabled), ANY(:item_ids)\n"
            "FROM sample_item item\nWHERE NOT EXISTS (\n"
            "    SELECT 1 FROM sample_child child\n"
            "    WHERE child.item_id = item.item_id AND child.enabled\n"
            ")\nORDER BY (item.rank <= :maximum_rank) DESC;"
        )

        self.assertEqual(ParenContentIndentRule().check(content, "generic.sql", {}), [])
        self.assertEqual(ParenMultiRule().check(content, "generic.sql", {}), [])
        self.assertEqual(ParenSingleRule().check(content, "generic.sql", {}), [])

    def test_multiline_lateral_and_exists_subqueries_are_indented(self):
        source = (
            "SELECT item.item_id\n"
            "FROM sample_item item\n"
            "LEFT JOIN LATERAL (\n"
            "SELECT child.value\n"
            "FROM sample_child child\n"
            "WHERE NOT EXISTS (\n"
            "  SELECT 1\n"
            "  FROM sample_exclusion exclusion\n"
            "  WHERE exclusion.child_id = child.child_id\n"
            ")\n"
            ") details ON true"
        )
        expected = (
            "SELECT item.item_id\n"
            "FROM sample_item item\n"
            "LEFT JOIN LATERAL (\n"
            "        SELECT child.value\n"
            "        FROM sample_child child\n"
            "        WHERE NOT EXISTS (\n"
            "            SELECT 1\n"
            "            FROM sample_exclusion exclusion\n"
            "            WHERE exclusion.child_id = child.child_id\n"
            "        )\n"
            "    ) details ON true"
        )

        rule = SubqueryIndentRule()
        fixed = rule.fix(source, "generic.sql", {})
        self.assertEqual(fixed, expected)
        self.assertEqual(rule.check(fixed, "generic.sql", {}), [])
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), fixed)

    def test_subquery_clauses_align_after_expanding_inline_subquery(self):
        content = (
            "SELECT item_id FROM sample_item WHERE state_id = (( SELECT state_id\n"
            "           FROM sample_state\n"
            "              WHERE state_code = :state_code));"
        )
        expected = (
            "SELECT item_id FROM sample_item WHERE state_id = ((\n"
            "    SELECT state_id\n"
            "    FROM sample_state\n"
            "    WHERE state_code = :state_code\n"
            "));"
        )

        fixed = SubqueryIndentRule().fix(content, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(SubqueryIndentRule().fix(fixed, "generic.sql", {}), fixed)

    def test_lateral_join_subquery_uses_join_continuation_indent(self):
        content = (
            "SELECT parent.item_id\n"
            "FROM\n"
            "    sample_parent parent\n"
            "    LEFT JOIN LATERAL (\n"
            "        SELECT child.parent_id\n"
            "        FROM sample_child child\n"
            "    ) child ON true;"
        )
        expected = (
            "SELECT parent.item_id\n"
            "FROM\n"
            "    sample_parent parent\n"
            "    LEFT JOIN LATERAL (\n"
            "            SELECT child.parent_id\n"
            "            FROM sample_child child\n"
            "        ) child ON true;"
        )

        rule = SubqueryIndentRule()
        fixed = rule.fix(content, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.check(fixed, "generic.sql", {}), [])
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), fixed)

    def test_single_statement_file_does_not_require_semicolon(self):
        content = "SELECT item_id FROM sample_item\n"

        self.assertEqual(StatementSemicolonRule().check(content, "generic.sql", {}), [])
        self.assertEqual(TrailingSemicolonRule().check(content, "generic.sql", {}), [])

    def test_short_multiline_where_is_compacted_when_it_fits(self):
        source = (
            "SELECT item_id FROM sample_item\n"
            "WHERE created_at >= :start\n"
            "    AND created_at < :end\n"
            "GROUP BY item_id"
        )
        expected = (
            "SELECT item_id FROM sample_item\n"
            "WHERE created_at >= :start AND created_at < :end\n"
            "GROUP BY item_id"
        )

        rule = WhereMultiRule()
        fixed = rule.fix(source, "generic.sql", {})
        self.assertEqual(fixed, expected)
        self.assertEqual(rule.check(fixed, "generic.sql", {}), [])
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), fixed)

    def test_returning_ends_where_clause_length_calculation(self):
        source = (
            "UPDATE sample_item\n"
            "SET item_name = :item_name\n"
            "WHERE\n"
            "    item_id = :item_id\n"
            "    AND item_version = :item_version\n"
            "RETURNING item_id, item_name"
        )
        expected = (
            "UPDATE sample_item\n"
            "SET item_name = :item_name\n"
            "WHERE item_id = :item_id AND item_version = :item_version\n"
            "RETURNING item_id, item_name"
        )

        rule = WhereMultiRule()
        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.check(fixed, "generic.sql", {}), [])
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), fixed)

    def test_filter_where_does_not_capture_following_join_conditions(self):
        source = (
            "SELECT count(*) FILTER (WHERE sample_item.enabled AND sample_item.visible)\n"
            "FROM sample_item\n"
            "LEFT JOIN sample_owner owner ON owner.owner_id = sample_item.owner_id\n"
            "    AND owner.enabled"
        )

        fixed = WhereMultiRule().fix(source, "generic.sql", {})

        self.assertIn("FILTER (WHERE sample_item.enabled AND sample_item.visible)", fixed)
        self.assertIn("\n    AND owner.enabled", fixed)

    def test_homogeneous_filter_predicate_keeps_required_parentheses(self):
        source = (
            "SELECT count(*) FILTER (WHERE sample_item.enabled AND sample_item.visible) "
            "FROM sample_item;"
        )

        rule = ParenSameOpRule()

        self.assertEqual(rule.check(source, "generic.sql", {}), [])
        self.assertEqual(rule.fix(source, "generic.sql", {}), source)

    def test_between_delimiter_is_not_a_boolean_condition_boundary(self):
        where_source = (
            "SELECT item_id FROM sample_item WHERE recorded_at BETWEEN :start\n"
            "    AND :end AND organization_identifier = :organization_identifier;"
        )
        where_expected = (
            "SELECT item_id FROM sample_item\n"
            "WHERE\n"
            "    recorded_at BETWEEN :start AND :end\n"
            "    AND organization_identifier = :organization_identifier;"
        )
        join_source = (
            "SELECT item.item_id FROM sample_item item JOIN sample_window window "
            "ON item.recorded_at BETWEEN window.start_at\n"
            "    AND window.end_at AND item.organization_identifier = window.organization_identifier;"
        )
        join_expected = (
            "SELECT item.item_id FROM sample_item item JOIN sample_window window\n"
            "    ON item.recorded_at BETWEEN window.start_at AND window.end_at\n"
            "    AND item.organization_identifier = window.organization_identifier;"
        )

        where_rule = WhereMultiRule()
        join_rule = JoinOnMultiRule()
        where_config = {"max_line_length": 80}
        self.assertEqual(where_rule.fix(where_source, "generic.sql", where_config), where_expected)
        self.assertEqual(join_rule.fix(join_source, "generic.sql", {}), join_expected)
        self.assertEqual(where_rule.check(where_expected, "generic.sql", where_config), [])
        self.assertEqual(join_rule.check(join_expected, "generic.sql", {}), [])

    def test_multiline_join_target_keeps_predicates_on_continuation_lines(self):
        source = (
            "SELECT item.item_id\n"
            "FROM sample_item item\n"
            "LEFT JOIN sample_owner_at(\n"
            "        :effective_at\n"
            "    ) owner ON owner.owner_id = item.owner_id AND owner.enabled"
        )
        expected = source.replace(
            "item.owner_id AND owner.enabled",
            "item.owner_id\n    AND owner.enabled",
        )

        rule = JoinOnMultiRule()
        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.check(fixed, "generic.sql", {}), [])

    def test_distinct_on_wraps_independently_from_projection_columns(self):
        rule = ColumnLayoutRule()
        compact = (
            "SELECT DISTINCT ON (item_id, created_at)\n"
            "    item_id,\n"
            "    created_at\n"
            "FROM sample_item;"
        )
        self.assertEqual(
            rule.fix(compact, "generic.sql", {}),
            "SELECT DISTINCT ON (item_id, created_at) item_id, created_at\n"
            "FROM sample_item;",
        )

        expanded = (
            "SELECT DISTINCT ON (organization_identifier, effective_timestamp, secondary_identifier) "
            "item_id, item_name FROM sample_item;"
        )
        self.assertEqual(
            rule.fix(expanded, "generic.sql", {"max_length": 60}),
            "SELECT DISTINCT ON (\n"
            "    organization_identifier,\n"
            "    effective_timestamp,\n"
            "    secondary_identifier\n"
            ")\n"
            "    item_id,\n"
            "    item_name FROM sample_item;",
        )

    def test_column_layout_preserves_whitespace_inside_literals(self):
        source = (
            "SELECT DISTINCT ON (item.category, 'keep  spaces')\n"
            "    item.category,\n"
            "    'also  keep' AS label\n"
            "FROM sample_item item;"
        )
        expected = (
            "SELECT DISTINCT ON (item.category, 'keep  spaces') "
            "item.category, 'also  keep' AS label\n"
            "FROM sample_item item;"
        )

        self.assertEqual(ColumnLayoutRule().fix(source, "generic.sql", {}), expected)

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

    def test_protected_signature_normalizes_cast_case_but_preserves_identity(self):
        original = "SELECT :county_fips::text[];"
        changed = "SELECT :county_fips::TEXT[];"

        self.assertEqual(
            protected_sql_signature(original), protected_sql_signature(changed)
        )

        custom_original = "SELECT payload::archive.custom_type[];"
        custom_changed = "SELECT payload::archive.other_type[];"
        self.assertNotEqual(
            protected_sql_signature(custom_original),
            protected_sql_signature(custom_changed),
        )

        standard_original = "SELECT CAST(:start AS timestamp with time zone);"
        standard_changed = "SELECT CAST(:start AS TIMESTAMP WITH TIME ZONE);"
        self.assertEqual(
            protected_sql_signature(standard_original),
            protected_sql_signature(standard_changed),
        )

        aliases = "SELECT :start::timestamptz, :label::varchar[];"
        canonical = (
            "SELECT :start::TIMESTAMP WITH TIME ZONE, "
            ":label::CHARACTER VARYING[];"
        )
        self.assertEqual(
            protected_sql_signature(aliases), protected_sql_signature(canonical)
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
