import unittest

from mir.rules.sql.additive_wrap import AdditiveWrapRule
from mir.rules.sql.union_layout import UnionLayoutRule
from mir.rules.sql.alias_as import AliasAsRule
from mir.rules.sql.as_spacing import ASSpacingRule
from mir.rules.sql.function_case import FunctionCaseRule
from mir.rules.sql.from_multi import FromMultiRule
from mir.rules.sql.expression_split import ExpressionSplitRule
from mir.rules.sql.clause_alignment import ClauseAlignmentRule
from mir.rules.sql.case_when_wrap import CaseWhenWrapRule
from mir.rules.sql.case_layout import CaseLayoutRule
from mir.rules.sql.column_layout import ColumnLayoutRule
from mir.rules.sql.comma_style import CommaStyleRule
from mir.rules.sql.join_on_multi import JoinOnMultiRule
from mir.rules.sql.keyword_case import KeywordCaseRule
from mir.rules.sql.line_length import LineLengthRule
from mir.rules.sql.named_parameters import NamedParametersRule
from mir.rules.sql.null_coalesce import NullCoalesceRule
from mir.rules.sql.operator_spacing import OperatorSpacingRule
from mir.rules.sql.paren_content_indent import ParenContentIndentRule
from mir.rules.sql.paren_multi import ParenMultiRule
from mir.rules.sql.paren_same_op import ParenSameOpRule
from mir.rules.sql.paren_single import ParenSingleRule
from mir.rules.sql.redundant_keywords import RedundantKeywordsRule
from mir.rules.sql.parenthesized_expression_wrap import ParenthesizedExpressionWrapRule
from mir.rules.sql.multiline_function_layout import MultilineFunctionLayoutRule
from mir.rules.sql.plpgsql_keyword_case import PlpgsqlKeywordCaseRule
from mir.rules.sql.sql_utils import _tokenize_sql_impl, protected_sql_signature, tokenize_sql
from mir.rules.sql.statement_semicolon import StatementSemicolonRule
from mir.rules.sql.subquery_indent import SubqueryIndentRule
from mir.rules.sql.table_function_indent import TableFunctionIndentRule
from mir.rules.sql.table_alias_as import TableAliasAsRule
from mir.rules.sql.trailing_semicolon import TrailingSemicolonRule
from mir.rules.sql.trailing_whitespace import TrailingWhitespaceRule
from mir.rules.sql.unresolved_alias import UnresolvedAliasRule
from mir.rules.sql.where_multi import WhereMultiRule


class TestSqlCompatibility(unittest.TestCase):
    def test_constraint_parentheses_are_not_removed(self):
        source = (
            "CREATE TABLE sample_item (\n"
            "    item_id INTEGER,\n"
            "    owner_id INTEGER,\n"
            "    PRIMARY KEY (item_id),\n"
            "    FOREIGN KEY (owner_id) REFERENCES sample_owner (owner_id),\n"
            "    UNIQUE (owner_id),\n"
            "    CHECK (item_id > 0)\n"
            ");"
        )

        rule = ParenSingleRule()

        self.assertEqual(rule.fix(source, "generic.sql", {}), source)
        self.assertEqual(rule.check(source, "generic.sql", {}), [])

    def test_trailing_whitespace_is_removed_without_changing_line_endings(self):
        source = "SELECT item_id  \r\nFROM sample_item;\t\r\n"
        expected = "SELECT item_id\r\nFROM sample_item;\r\n"
        rule = TrailingWhitespaceRule()

        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), expected)

    def test_multiline_case_stays_with_its_leading_additive_operator(self):
        source = (
            "    first_label\n"
            "        || CASE WHEN category = 'primary' THEN 'one' "
            "WHEN category = 'secondary' THEN 'two' ELSE 'other' END"
        )
        expected = (
            "    first_label\n"
            "        || CASE\n"
            "            WHEN category = 'primary' THEN 'one'\n"
            "            WHEN category = 'secondary' THEN 'two'\n"
            "            ELSE 'other'\n"
            "        END"
        )
        rule = CaseLayoutRule()

        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), expected)

    def test_column_layout_preserves_additive_case_continuation_levels(self):
        source = (
            "SELECT\n"
            "    item_id,\n"
            "    label_prefix\n"
            "        || CASE\n"
            "            WHEN category = 'primary' THEN 'one'\n"
            "            ELSE 'other'\n"
            "        END AS label,\n"
            "    created_at\n"
            "FROM sample_item"
        )
        rule = ColumnLayoutRule()

        self.assertEqual(rule.fix(source, "generic.sql", {}), source)
        self.assertEqual(rule.check(source, "generic.sql", {}), [])

    def test_column_layout_uses_full_line_limit_for_case_compaction(self):
        source = (
            "            SELECT\n"
            "                item_id,\n"
            "                slot_number,\n"
            "                CASE WHEN run_count = 1 THEN 1 ELSE run_count + 1 END AS required_count\n"
            "            FROM sample_item"
        )
        expected = (
            "            SELECT item_id, slot_number, "
            "CASE WHEN run_count = 1 THEN 1 ELSE run_count + 1 END AS required_count\n"
            "            FROM sample_item"
        )
        rule = ColumnLayoutRule()

        fixed = rule.fix(source, "generic.sql", {})
        self.assertEqual(fixed, expected)
        self.assertEqual(rule.check(fixed, "generic.sql", {}), [])

    def test_plpgsql_message_level_can_be_a_sql_identifier(self):
        source = "WITH info AS (SELECT item_id FROM sample_item) SELECT * FROM info;"
        rule = PlpgsqlKeywordCaseRule()

        self.assertEqual(rule.fix(source, "generic.sql", {}), source)
        self.assertEqual(rule.check(source, "generic.sql", {}), [])

    def test_full_outer_join_keeps_outer_keyword(self):
        source = "SELECT * FROM first_item FULL OUTER JOIN second_item USING (item_id);"
        rule = RedundantKeywordsRule()

        self.assertEqual(rule.fix(source, "generic.sql", {}), source)
        self.assertEqual(rule.check(source, "generic.sql", {}), [])

    def test_dynamic_join_conditions_compact_within_one_xml_branch(self):
        source = (
            "    JOIN sample_owner owner ON owner.id = item.owner_id\n"
            "        AND owner.active"
        )
        expected = (
            "    JOIN sample_owner owner ON owner.id = item.owner_id AND owner.active"
        )
        and_offset = source.index("AND")
        rule = JoinOnMultiRule()
        config = {
            "mybatis_dynamic_offsets": set(range(and_offset, len(source))),
            "mybatis_boundary_offsets": set(),
        }

        self.assertEqual(rule.fix(source, "generic.xml", config), expected)

    def test_wrapped_join_operator_keeps_its_condition_on_the_same_line(self):
        source = (
            "    JOIN sample_owner owner ON owner.organization_identifier = item.organization_identifier\n"
            "        AND\n"
            "owner.external_identifier = item.owner_external_identifier"
        )
        expected = (
            "    JOIN sample_owner owner ON owner.organization_identifier = item.organization_identifier\n"
            "        AND owner.external_identifier = item.owner_external_identifier"
        )
        rule = JoinOnMultiRule()

        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), expected)

    def test_join_predicate_subquery_compacts_when_on_line_fits(self):
        source = (
            "                            LEFT JOIN sample_county county\n"
            "                                ON county.state_id = (\n"
            "                                    SELECT state_id\n"
            "                                    FROM sample_state\n"
            "                                    WHERE code = 'AA'\n"
            "                                )"
        )
        expected = (
            "                            LEFT JOIN sample_county county\n"
            "                                ON county.state_id = "
            "(SELECT state_id FROM sample_state WHERE code = 'AA')"
        )
        rule = SubqueryIndentRule()

        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), expected)

    def test_additive_wrap_uses_join_continuation_limit(self):
        source = (
            "            JOIN sample_window window ON item.recorded_at "
            "BETWEEN window.start_at AND window.start_at + window.duration"
        )
        rule = AdditiveWrapRule()

        self.assertGreater(len(source), 100)
        self.assertLessEqual(len(source), 120)
        self.assertEqual(rule.fix(source, "generic.sql", {}), source)

    def test_additive_wrap_uses_join_limit_after_multiline_target(self):
        source = (
            "                ) generated_time ON recorded_at BETWEEN generated_time "
            "AND generated_time + interval_length"
        )
        rule = AdditiveWrapRule()

        self.assertGreater(len(source), 100)
        self.assertLessEqual(len(source), 120)
        self.assertEqual(rule.fix(source, "generic.sql", {}), source)

    def test_additive_wrap_leaves_join_predicate_continuation_to_join_rules(self):
        source = (
            "            JOIN generated_window window ON recorded_at BETWEEN window.start_at AND window.start_at\n"
            "                + window.duration"
        )
        rule = AdditiveWrapRule()

        self.assertEqual(rule.fix(source, "generic.sql", {}), source)

    def test_case_after_additive_operator_stays_on_expression_line(self):
        from mir.rules.sql.case_layout import CaseLayoutRule

        source = (
            "    base_count_with_descriptive_name + CASE\n"
            "        WHEN include_additional_count THEN additional_count_with_descriptive_name\n"
            "        ELSE 0\n"
            "    END"
        )
        rule = CaseLayoutRule()

        self.assertEqual(rule.fix(source, "generic.sql", {}), source)
        self.assertEqual(rule.check(source, "generic.sql", {}), [])

    def test_multiline_update_keeps_semicolon_with_last_assignment(self):
        from mir.rules.sql.update_layout import UpdateLayoutRule

        source = (
            "UPDATE sample_calculation\n"
            "SET first_result = first_source,\n"
            "    second_result = second_source\n"
            ";"
        )
        expected = source.replace(
            "SET first_result", "SET\n    first_result"
        ).replace("second_source\n;", "second_source;")
        rule = UpdateLayoutRule()

        config = {"max_length": 60}
        fixed = rule.fix(source, "generic.sql", config)
        self.assertEqual(fixed, expected)
        self.assertEqual(rule.fix(fixed, "generic.sql", config), expected)

    def test_nullable_equality_accepts_reversed_equality_operands(self):
        source = (
            "((left_item.owner_id IS NULL AND right_item.owner_id IS NULL) OR "
            "right_item.owner_id = left_item.owner_id)"
        )
        expected = (
            "COALESCE(right_item.owner_id, -1) = "
            "COALESCE(left_item.owner_id, -1)"
        )

        rule = NullCoalesceRule()

        self.assertEqual(rule.fix(source, "generic.sql", {}), expected)

    def test_nullable_equality_unwraps_parenthesized_equality_branch(self):
        source = (
            "((left_item.owner_id IS NULL AND right_item.owner_id IS NULL) OR "
            "(right_item.owner_id = left_item.owner_id))"
        )
        expected = (
            "COALESCE(right_item.owner_id, -1) = "
            "COALESCE(left_item.owner_id, -1)"
        )

        rule = NullCoalesceRule()

        self.assertEqual(rule.fix(source, "generic.sql", {}), expected)

    def test_boolean_null_fallback_does_not_use_numeric_coalesce(self):
        source = "enabled IS NULL OR enabled = true"

        rule = NullCoalesceRule()

        self.assertEqual(rule.fix(source, "generic.sql", {}), source)
        self.assertEqual(rule.check(source, "generic.sql", {}), [])

    def test_standalone_set_returning_function_alias_preserves_omitted_as(self):
        source = "SELECT * FROM generate_series(1, 3) item_number;"
        expected = source

        rule = TableAliasAsRule()

        self.assertEqual(rule.fix(source, "generic.sql", {}), expected)
        self.assertEqual(rule.fix(expected, "generic.sql", {}), expected)

    def test_joined_set_returning_function_alias_preserves_as(self):
        source = (
            "SELECT * FROM sample_item "
            "CROSS JOIN generate_series(1, 3) AS item_number;"
        )
        expected = source

        rule = TableAliasAsRule()

        self.assertEqual(rule.fix(source, "generic.sql", {}), expected)
        self.assertEqual(rule.fix(expected, "generic.sql", {}), expected)

    def test_distinct_on_projection_is_not_treated_as_an_alias(self):
        source = (
            "SELECT DISTINCT ON (recorded_date)\n"
            "    recorded_date, item_count\n"
            "FROM sample_item;"
        )

        rule = AliasAsRule()

        self.assertEqual(rule.fix(source, "generic.sql", {}), source)
        self.assertEqual(rule.check(source, "generic.sql", {}), [])

    def test_short_alias_recombines_in_mybatis_sql(self):
        source = "    item_name\n                    AS display_name"
        expected = "    item_name AS display_name"

        rule = ASSpacingRule()
        config = {"original_xml": "<mapper />"}

        self.assertEqual(rule.fix(source, "generic.xml", config), expected)
        self.assertEqual(rule.fix(expected, "generic.xml", config), expected)

    def test_empty_mybatis_dynamic_offsets_allow_group_by_expansion(self):
        source = (
            "    GROUP BY first_grouping_column, second_grouping_column, "
            "third_grouping_column, fourth_grouping_column"
        )
        expected = (
            "    GROUP BY\n"
            "        first_grouping_column,\n"
            "        second_grouping_column,\n"
            "        third_grouping_column,\n"
            "        fourth_grouping_column"
        )
        config = {
            "max_length": 80,
            "mybatis_dynamic_offsets": set(),
            "original_xml": "<mapper />",
        }
        rule = ColumnLayoutRule()

        self.assertEqual(rule.fix(source, "generic.xml", config), expected)
        self.assertEqual(rule.fix(expected, "generic.xml", config), expected)

    def test_case_layout_keeps_a_short_boolean_condition_together(self):
        source = (
            "CASE WHEN enabled AND coalesce(visible, true) THEN "
            "calculate_item_count_with_a_long_name(item_id) ELSE\n    0 END"
        )
        expected = (
            "CASE\n"
            "    WHEN enabled AND coalesce(visible, true)\n"
            "        THEN calculate_item_count_with_a_long_name(item_id)\n"
            "    ELSE 0\n"
            "END"
        )

        rule = CaseLayoutRule()
        fixed = rule.fix(source, "generic.sql", {"max_length": 80})

        self.assertEqual(fixed, expected)
        self.assertEqual(
            rule.fix(fixed, "generic.sql", {"max_length": 80}),
            expected,
        )

    def test_short_multiline_case_condition_compacts_root_boolean(self):
        source = (
            "    WHEN enabled\n"
            "        AND coalesce(visible, true) THEN item_count"
        )
        expected = "    WHEN enabled AND coalesce(visible, true) THEN item_count"

        rule = CaseWhenWrapRule()

        self.assertEqual(rule.fix(source, "generic.sql", {}), expected)
        self.assertEqual(rule.fix(expected, "generic.sql", {}), expected)

    def test_case_layout_counts_the_trailing_alias_in_the_line_limit(self):
        source = (
            "                                    CASE WHEN "
            "(sum(item_count) IS NULL) THEN false ELSE true END "
            "AS has_summary_data_flag"
        )
        expected = (
            "                                    CASE\n"
            "                                        WHEN (sum(item_count) IS NULL) THEN false\n"
            "                                        ELSE true\n"
            "                                    END AS has_summary_data_flag"
        )

        rule = CaseLayoutRule()
        fixed = rule.fix(
            source,
            "generic.xml",
            {"base_indent": "        ", "original_xml": "<mapper />"},
        )

        self.assertEqual(fixed, expected)
        self.assertEqual(
            rule.fix(
                fixed,
                "generic.xml",
                {"base_indent": "        ", "original_xml": "<mapper />"},
            ),
            expected,
        )

    def test_expression_split_defers_single_line_case_arm_layout(self):
        source = (
            "                                        CASE WHEN "
            "(sum(item_count_with_a_long_name) IS NULL) THEN false ELSE true END "
            "AS has_summary_data"
        )

        self.assertEqual(ExpressionSplitRule().fix(source, "generic.sql", {}), source)

    def test_line_length_defers_single_line_case_arm_layout(self):
        source = (
            "                                        CASE WHEN "
            "(sum(item_count_with_a_long_name) IS NULL) THEN false ELSE true END "
            "AS has_summary_data"
        )

        self.assertEqual(LineLengthRule().fix(source, "generic.sql", {}), source)

    def test_case_function_null_predicate_grouping_is_preserved(self):
        source = "CASE WHEN (sum(item_count) IS NULL) THEN false ELSE true END"

        rule = ParenSingleRule()

        self.assertEqual(rule.fix(source, "generic.sql", {}), source)
        self.assertEqual(rule.check(source, "generic.sql", {}), [])

    def test_line_length_does_not_compact_multiline_in_subquery(self):
        source = (
            "AND county_id IN (\n"
            "    SELECT county_id\n"
            "    FROM sample_county\n"
            "    WHERE\n"
            "        county_code IN\n"
            "            #{code}\n"
            ")"
        )

        rule = LineLengthRule()

        self.assertEqual(rule.fix(source, "generic.sql", {}), source)

    def test_line_length_defers_long_join_boolean_to_join_layout(self):
        source = (
            "JOIN sample_customer customer ON customer.item_id = sample_item.item_id "
            "AND coalesce(customer.organization_identifier, -1) = "
            "coalesce(sample_item.organization_identifier, -1)"
        )
        rule = LineLengthRule()

        self.assertGreater(len(source), 120)
        self.assertEqual(rule.fix(source, "generic.sql", {}), source)

    def test_redundant_multiplicative_operand_parentheses_are_removed(self):
        source = (
            "SELECT (((peak_count - current_count)::NUMERIC / greatest(peak_count, 1)) "
            "- ((peak_count - prior_count)::NUMERIC / greatest(peak_count, 1))) AS progress"
        )
        expected = (
            "SELECT ((peak_count - current_count)::NUMERIC / greatest(peak_count, 1) "
            "- (peak_count - prior_count)::NUMERIC / greatest(peak_count, 1)) AS progress"
        )

        rule = ParenSingleRule()
        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), expected)

    def test_multiline_parenthesized_arithmetic_aligns_operators(self):
        source = (
            "(\n"
            "    (peak_measure - current_measure)::NUMERIC / greatest(peak_measure, 1) -\n"
            "    (peak_measure - previous_measure_with_an_exceptionally_long_name)::NUMERIC / greatest(peak_measure, 1)\n"
            ")"
        )
        expected = (
            "(\n"
            "    (peak_measure - current_measure)::NUMERIC / greatest(peak_measure, 1)\n"
            "    - (peak_measure - previous_measure_with_an_exceptionally_long_name)::NUMERIC\n"
            "    / greatest(peak_measure, 1)\n"
            ")"
        )

        rule = ParenthesizedExpressionWrapRule()
        first = rule.fix(source, "generic.sql", {})
        fixed = rule.fix(first, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), expected)

    def test_parenthesized_expression_does_not_reflow_query_block_operators(self):
        source = (
            "(\n"
            "    SELECT run_start_time\n"
            "    FROM sample_summary\n"
            "    WHERE run_start_time BETWEEN :end_time - '1 day'::interval\n"
            "        AND :end_time\n"
            ")"
        )
        rule = ParenthesizedExpressionWrapRule()

        self.assertEqual(rule.fix(source, "generic.sql", {}), source)

    def test_additive_continuations_align_and_join_a_stranded_operand(self):
        source = (
            "    first_value + second_value\n"
            "           + third_value +\n"
            "                 fourth_value"
        )
        expected = (
            "    first_value + second_value\n"
            "        + third_value + fourth_value"
        )

        rule = AdditiveWrapRule()
        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), expected)
        self.assertEqual(rule.check(fixed, "generic.sql", {}), [])

    def test_additive_trailing_operator_moves_before_a_long_final_operand(self):
        source = (
            "    first_measure_with_long_name + second_measure_with_long_name +\n"
            "                 third_measure +\n"
            "                 fourth_measure"
        )
        expected = (
            "    first_measure_with_long_name + second_measure_with_long_name\n"
            "        + third_measure + fourth_measure"
        )

        rule = AdditiveWrapRule()
        config = {
            "max_line_length": 80,
            "continuation_max_line_length": 80,
        }
        fixed = rule.fix(source, "generic.sql", config)

        self.assertEqual(fixed, expected)
        self.assertEqual(
            rule.fix(fixed, "generic.sql", config),
            expected,
        )

    def test_additive_adjacent_continuation_lines_compact_when_they_fit(self):
        source = (
            "    first_measure + second_measure\n"
            "        + third_measure\n"
            "        + fourth_measure"
        )
        expected = (
            "    first_measure + second_measure\n"
            "        + third_measure + fourth_measure"
        )

        rule = AdditiveWrapRule()
        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), expected)

    def test_additive_first_continuation_rejoins_base_line_when_it_fits(self):
        source = (
            "    first_measure\n"
            "        + second_measure\n"
            "        + third_measure_with_a_long_name + fourth_measure"
        )
        expected = (
            "    first_measure + second_measure\n"
            "        + third_measure_with_a_long_name + fourth_measure"
        )

        rule = AdditiveWrapRule()
        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), expected)
        self.assertEqual(rule.check(fixed, "generic.sql", {}), [])

    def test_union_following_query_aligns_with_set_operator(self):
        source = (
            "    SELECT item_id\n"
            "    FROM current_item\n"
            "    UNION ALL\n"
            "            SELECT item_id\n"
            "            FROM archived_item"
        )
        expected = source.replace(
            "            SELECT item_id\n"
            "            FROM archived_item",
            "    SELECT item_id\n"
            "    FROM archived_item",
        )

        rule = UnionLayoutRule()
        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), expected)
        self.assertEqual(rule.check(fixed, "generic.sql", {}), [])

    def test_join_expands_a_mixed_boolean_group(self):
        source = (
            "    JOIN customer_counts counts ON counts.state_id = state.id "
            "AND (NOT :by_county OR counts.county_id = county.id)"
        )
        expected = (
            "    JOIN customer_counts counts ON counts.state_id = state.id\n"
            "        AND (\n"
            "            NOT :by_county\n"
            "            OR counts.county_id = county.id\n"
            "        )"
        )

        rule = JoinOnMultiRule()
        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), expected)
        self.assertEqual(rule.check(fixed, "generic.sql", {}), [])
        self.assertEqual(LineLengthRule().fix(expected, "generic.sql", {}), expected)

    def test_table_function_preserves_case_nesting(self):
        source = (
            "FROM generate_series(\n"
            "    :start_time,\n"
            "    CASE\n"
            "    WHEN :hours > 0 THEN :hours\n"
            "    ELSE 1\n"
            "    END\n"
            ") AS generated_time"
        )
        expected = (
            "FROM generate_series(\n"
            "    :start_time,\n"
            "    CASE\n"
            "        WHEN :hours > 0 THEN :hours\n"
            "        ELSE 1\n"
            "    END\n"
            ") AS generated_time"
        )

        rule = TableFunctionIndentRule()
        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), expected)

    def test_explicit_window_order_direction_is_preserved(self):
        source = (
            "SELECT lag(item_count) OVER (PARTITION BY item_type "
            "ORDER BY recorded_at ASC) FROM sample_item ORDER BY item_type ASC;"
        )
        expected = (
            "SELECT lag(item_count) OVER (PARTITION BY item_type "
            "ORDER BY recorded_at ASC) FROM sample_item ORDER BY item_type;"
        )

        rule = RedundantKeywordsRule()
        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.check(fixed, "generic.sql", {}), [])

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

    def test_multiline_where_aligns_split_operand_and_compacts_short_or_arm(self):
        source = (
            "                                        WHERE\n"
            "                                            recorded_timestamp_for_requested_interval =\n"
            "                                                   timezone('utc', :interval_start) - INTERVAL '15 minutes'\n"
            "                                            OR\n"
            "                                                   recorded_timestamp_for_requested_interval = :interval_start\n"
            "                                        GROUP BY item_id"
        )
        expected = (
            "                                        WHERE\n"
            "                                            recorded_timestamp_for_requested_interval =\n"
            "                                                timezone('utc', :interval_start) - INTERVAL '15 minutes'\n"
            "                                            OR recorded_timestamp_for_requested_interval = :interval_start\n"
            "                                        GROUP BY item_id"
        )
        rule = WhereMultiRule()

        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), expected)

    def test_multiline_where_wraps_comparison_at_encoded_source_limit(self):
        source = (
            "        WHERE\n"
            "            account.enabled\n"
            "            AND date_trunc('day', now() + make_interval(days => :maximum_days)) "
            ">= date_trunc('day', account.expiration_date)\n"
            "            AND audit.id IS NULL"
        )
        expected = (
            "        WHERE\n"
            "            account.enabled\n"
            "            AND date_trunc('day', now() + make_interval(days => :maximum_days)) >=\n"
            "                date_trunc('day', account.expiration_date)\n"
            "            AND audit.id IS NULL"
        )
        rule = WhereMultiRule()
        config = {"original_xml": "<mapper />", "max_line_length": 120}

        fixed = rule.fix(source, "generic.xml", config)

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.fix(fixed, "generic.xml", config), expected)

    def test_multiline_single_row_values_puts_each_value_on_its_own_line(self):
        source = (
            "INSERT INTO sample_item (item_id, item_name, owner_id)\n"
            "VALUES (:item_id, :item_name,\n"
            "      :owner_id)"
        )
        expected = (
            "INSERT INTO sample_item (item_id, item_name, owner_id)\n"
            "VALUES (\n"
            "    :item_id,\n"
            "    :item_name,\n"
            "    :owner_id\n"
            ")"
        )
        rule = MultilineFunctionLayoutRule()

        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), expected)

    def test_parenthesized_boolean_group_uses_where_continuations(self):
        source = (
            "WHERE\n"
            "    (\n"
            "        recorded_timestamp_for_requested_interval =\n"
            "               timezone('utc', :interval_start) - INTERVAL '15 minutes'\n"
            "        OR\n"
            "               recorded_timestamp_for_requested_interval = :interval_start\n"
            "    )\n"
            "    AND owner_id < 9000"
        )
        expected = (
            "WHERE\n"
            "    (\n"
            "        recorded_timestamp_for_requested_interval =\n"
            "            timezone('utc', :interval_start) - INTERVAL '15 minutes'\n"
            "        OR recorded_timestamp_for_requested_interval = :interval_start\n"
            "    )\n"
            "    AND owner_id < 9000"
        )
        rule = ParenMultiRule()

        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), expected)

        self.assertEqual(
            ParenthesizedExpressionWrapRule().fix(expected, "generic.sql", {}),
            expected,
        )

    def test_long_overlaps_row_wraps_before_nested_calls(self):
        source = (
            "    AND (valid_from, valid_to) OVERLAPS "
            "(timezone('utc', :interval_start), "
            "timezone('utc', :interval_end_with_a_long_name))"
        )
        expected = (
            "    AND (valid_from, valid_to) OVERLAPS (\n"
            "        timezone('utc', :interval_start),\n"
            "        timezone('utc', :interval_end_with_a_long_name)\n"
            "    )"
        )
        rule = ParenthesizedExpressionWrapRule()

        fixed = rule.fix(source, "generic.sql", {"max_line_length": 100})

        self.assertEqual(fixed, expected)
        self.assertEqual(
            rule.fix(fixed, "generic.sql", {"max_line_length": 100}),
            expected,
        )

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

    def test_case_arm_uses_the_full_configured_line_length(self):
        source = (
            "                                WHEN event.recorded_at = "
            "timezone('utc', :interval_start_time) THEN 'current_event'"
        )
        self.assertGreater(len(source), 110)
        self.assertLessEqual(len(source), 120)

        self.assertEqual(CaseWhenWrapRule().fix(source, "generic.sql", {}), source)

    def test_long_case_condition_aligns_root_boolean_and_then(self):
        source = (
            "                WHEN TRUE = ANY(SELECT unnest(collected_counts) IS NULL) "
            "AND array_length(collected_counts, 1) > 1 THEN 'mixed'"
        )
        expected = (
            "                WHEN TRUE = ANY(SELECT unnest(collected_counts) IS NULL) "
            "AND array_length(collected_counts, 1) > 1\n"
            "                    THEN 'mixed'"
        )

        self.assertEqual(CaseWhenWrapRule().fix(source, "generic.sql", {}), expected)

    def test_long_case_result_does_not_split_a_short_boolean_condition(self):
        source = (
            "                    WHEN u.active AND coalesce(su.active, true) "
            "THEN coalesce(ucc.collected_count, ucc.model_count, 0)"
        )
        expected = source

        self.assertEqual(CaseWhenWrapRule().fix(source, "generic.sql", {}), expected)

    def test_multiline_case_keywords_follow_the_case_indent(self):
        source = (
            "        CASE\n"
            "        WHEN interval_hours > 0 THEN interval_hours\n"
            "        ELSE 1\n"
            "        END"
        )
        expected = (
            "        CASE\n"
            "            WHEN interval_hours > 0 THEN interval_hours\n"
            "            ELSE 1\n"
            "        END"
        )

        rule = CaseWhenWrapRule()
        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), expected)

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

        where_rule = WhereMultiRule()
        self.assertEqual(where_rule.fix(source, "generic.sql", {}), source)
        self.assertEqual(where_rule.fix(expected, "generic.sql", {}), expected)

    def test_long_filter_predicate_uses_multiline_where_layout(self):
        source = (
            "        count(*) FILTER (\n"
            "            WHERE direct_customers IS NOT NULL "
            "AND snapshot_customers IS NOT NULL "
            "AND direct_customers > snapshot_customers\n"
            "        ) AS direct_selected"
        )
        expected = (
            "        count(*) FILTER (\n"
            "            WHERE\n"
            "                direct_customers IS NOT NULL\n"
            "                AND snapshot_customers IS NOT NULL\n"
            "                AND direct_customers > snapshot_customers\n"
            "        ) AS direct_selected"
        )

        rule = WhereMultiRule()
        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), expected)

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

    def test_join_preserves_a_multiline_grouped_condition(self):
        source = (
            "LEFT JOIN sample_counts counts ON counts.owner_id = owner.id AND (\n"
            "    counts.category_id = category.id OR counts.category_id IS NULL\n"
            ")"
        )
        expected = (
            "LEFT JOIN sample_counts counts ON counts.owner_id = owner.id\n"
            "    AND (\n"
            "        counts.category_id = category.id\n"
            "        OR counts.category_id IS NULL\n"
            "    )"
        )

        rule = JoinOnMultiRule()
        fixed = rule.fix(source, "generic.sql", {"max_line_length": 100})

        self.assertEqual(fixed, expected)
        self.assertEqual(
            rule.fix(fixed, "generic.sql", {"max_line_length": 100}),
            expected,
        )

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

    def test_clause_alignment_keeps_mybatis_branches_independent(self):
        source = (
            "            SELECT item_id\n"
            "            FROM current_item\n"
            "            UNION ALL\n"
            "                    SELECT item_id\n"
            "                    FROM archived_item\n"
            "                    WHERE archived"
        )
        branch_start = source.index("                    SELECT", source.index("UNION ALL"))
        config = {
            "mybatis_boundary_offsets": set(),
            "mybatis_dynamic_offsets": set(range(branch_start, len(source))),
        }
        rule = ClauseAlignmentRule()

        self.assertEqual(rule.check(source, "generic.xml", config), [])
        self.assertEqual(rule.fix(source, "generic.xml", config), source)

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

    def test_insert_target_columns_align_with_insert_statement(self):
        source = (
            "        INSERT INTO sample.target_item (\n"
            "                item_id,\n"
            "                item_name\n"
            "            )\n"
            "            SELECT item_id, item_name FROM pending_item;"
        )
        expected = (
            "        INSERT INTO sample.target_item(\n"
            "            item_id,\n"
            "            item_name\n"
            "        )\n"
            "            SELECT item_id, item_name FROM pending_item;"
        )
        rule = ParenContentIndentRule()

        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.check(fixed, "generic.sql", {}), [])
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), fixed)

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

    def test_join_subquery_opener_stays_with_join_keyword(self):
        source = (
            "SELECT parent.item_id\n"
            "FROM\n"
            "    sample_parent parent\n"
            "    LEFT JOIN\n"
            "        (\n"
            "            SELECT child.parent_id\n"
            "            FROM sample_child child\n"
            "        ) child ON true;"
        )
        expected = (
            "SELECT parent.item_id\n"
            "FROM\n"
            "    sample_parent parent\n"
            "    LEFT JOIN (\n"
            "            SELECT child.parent_id\n"
            "            FROM sample_child child\n"
            "        ) child ON true;"
        )

        rule = SubqueryIndentRule()
        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), expected)

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

    def test_case_arm_does_not_inherit_boolean_operators_from_later_clauses(self):
        source = (
            "SELECT CASE WHEN (enabled AND (visible OR public)) THEN 1 ELSE 0 END "
            "FROM sample_item WHERE owner_id = :owner_id OR shared;"
        )
        expected = source.replace(
            "WHEN (enabled AND (visible OR public))",
            "WHEN enabled AND (visible OR public)",
        )
        rule = ParenSameOpRule()

        self.assertEqual(rule.fix(source, "generic.sql", {}), expected)
        self.assertEqual(rule.check(expected, "generic.sql", {}), [])

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

    def test_multiline_table_function_keeps_predicates_on_continuation_lines(self):
        source = (
            "SELECT item.item_id\n"
            "FROM sample_item item\n"
            "LEFT JOIN sample_owner_at(\n"
            "        :effective_at\n"
            "    ) owner ON owner.owner_id = item.owner_id AND owner.enabled"
        )
        rule = JoinOnMultiRule()
        fixed = rule.fix(source, "generic.sql", {})

        expected = source.replace(
            "item.owner_id AND owner.enabled",
            "item.owner_id\n    AND owner.enabled",
        )
        self.assertEqual(fixed, expected)
        self.assertEqual(rule.check(fixed, "generic.sql", {}), [])

    def test_multiline_derived_table_compacts_predicates_when_they_fit(self):
        source = (
            "SELECT item.item_id\n"
            "FROM sample_item item\n"
            "LEFT JOIN (\n"
            "        SELECT owner_id, enabled\n"
            "        FROM sample_owner\n"
            "    ) owner ON owner.owner_id = item.owner_id\n"
            "    AND owner.enabled"
        )
        expected = source.replace(
            "item.owner_id\n    AND owner.enabled",
            "item.owner_id AND owner.enabled",
        )

        rule = JoinOnMultiRule()
        fixed = rule.fix(source, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), expected)
        self.assertEqual(rule.check(fixed, "generic.sql", {}), [])

    def test_join_predicate_at_line_limit_stays_inline(self):
        source = (
            "                LEFT JOIN sample_running_calculation_handlers_long handler "
            "ON handler.handler_id = state_utility_handler"
        )
        rule = JoinOnMultiRule()

        self.assertEqual(len(source), 120)
        self.assertEqual(rule.fix(source, "generic.sql", {}), source)

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

    def test_protected_signature_rejects_corrupted_keyword_identifier(self):
        original = "SELECT item_id FROM sample_item WHERE enabled AND ready;"
        corrupted = "SELECT item_id FROM sample_item WHERE enabled ANDnd ready;"

        self.assertNotEqual(
            protected_sql_signature(original),
            protected_sql_signature(corrupted),
        )

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
