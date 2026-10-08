import unittest
from unittest.mock import patch

from mir.engine.config import Config
from mir.engine.rule_interface import BaseRule, Violation
from mir.engine.runner import process_document
from mir.engine.selection import expand_selection
from mir.rules.sql.trellis_directives import TrellisDirectivesRule
from mir.rules.sql.trellis_indent import TrellisIndentRule
from mir.rules.sql.trellis_utils import (
    has_trellis_syntax,
    parse_directive,
    trellis_directive_signature,
)


class DirectiveRemovingRule(BaseRule):
    rule_id = "IR-test-remove-trellis-directive"
    description = "Test the Trellis semantic safety boundary."
    category = "tests"
    is_fixable = "yes"
    enabled_by_default = True
    commit_profile = True
    trellis_safe = True

    def check(self, content, file_path, rule_config):
        return [Violation(self.rule_id, 2, self.description, [content.splitlines()[1]], True)]

    def fix(self, content, file_path, rule_config):
        return content.replace("-- trellis: if enabled\n", "")


class TestTrellisSupport(unittest.TestCase):
    def test_named_bind_external_sql_is_detected_as_trellis(self):
        self.assertTrue(has_trellis_syntax("SELECT item_id FROM sample_table WHERE item_id = :item_id"))
        self.assertTrue(has_trellis_syntax("SELECT :start::timestamp"))
        self.assertFalse(has_trellis_syntax("SELECT 1::integer"))

    def test_all_supported_directive_families_are_accepted(self):
        content = """SELECT item_id
FROM sample_table
-- trellis: if filters.enabled
WHERE item_state = :filters.state
-- trellis: elif include_archived
OR archived_at IS NOT NULL
-- trellis: else
AND item_state IS NOT NULL
-- trellis: endif
-- trellis: choose sort_mode
-- trellis: when "name"
ORDER BY item_name
-- trellis: otherwise
ORDER BY item_id
-- trellis: endchoose
-- trellis: for item in item_ids separator=","
:item
-- trellis: endfor
"""

        self.assertEqual(TrellisDirectivesRule().check(content, "generic.sql", {}), [])

    def test_directive_parser_accepts_tab_separated_keyword_and_expression(self):
        directive = parse_directive("-- trellis: if\tenabled", 1)

        self.assertIsNotNone(directive)
        self.assertEqual((directive.keyword, directive.argument), ("if", "enabled"))
        self.assertEqual(directive.canonical, "-- trellis: if enabled")

    def test_directive_signature_ignores_layout_but_not_semantics(self):
        original = "--trellis:IF enabled\nSELECT 1\n-- trellis: endif\n"
        formatted = "    -- trellis: if enabled\nSELECT 1\n    -- trellis: endif\n"
        changed = "-- trellis: if disabled\nSELECT 1\n-- trellis: endif\n"

        self.assertEqual(trellis_directive_signature(original), trellis_directive_signature(formatted))
        self.assertNotEqual(trellis_directive_signature(original), trellis_directive_signature(changed))

    def test_commit_profile_rejects_changed_directive_semantics(self):
        content = "SELECT item_id\n-- trellis: if enabled\nFROM sample_item\n-- trellis: endif\n"
        config = Config()
        config.profile = "commit"
        config.fix = True

        with patch("mir.engine.runner.load_rules_for_language", return_value=[DirectiveRemovingRule()]):
            result = process_document(config, content, "generic.sql", "sql")

        self.assertEqual(result.content, content)
        self.assertEqual(
            result.diagnostics,
            [
                "Unsafe fix rejected for IR-test-remove-trellis-directive on generic.sql: "
                "Trellis directive semantics changed"
            ],
        )

    def test_trellis_parenthesis_indentation_aligns_directive_lines(self):
        content = (
            "WHERE\n"
            "    TRUE\n"
            "    -- trellis: if item_ids\n"
            "    AND item_id IN (\n"
            "-- trellis: for item in item_ids separator=\",\"\n"
            "      :item\n"
            "-- trellis: endfor\n"
            "  )\n"
            "    -- trellis: endif\n"
        )
        expected = (
            "WHERE\n"
            "    TRUE\n"
            "    -- trellis: if item_ids\n"
            "        AND item_id IN (\n"
            "            -- trellis: for item in item_ids separator=\",\"\n"
            "                :item\n"
            "            -- trellis: endfor\n"
            "        )\n"
            "    -- trellis: endif\n"
        )
        rule = TrellisIndentRule()

        fixed = rule.fix(content, "generic.sql", {})

        self.assertEqual(fixed, expected)
        self.assertEqual(rule.check(fixed, "generic.sql", {}), [])
        self.assertEqual(rule.fix(fixed, "generic.sql", {}), fixed)
        self.assertEqual(trellis_directive_signature(content), trellis_directive_signature(fixed))

    def test_trellis_indent_does_not_format_named_bind_sql_without_directives(self):
        content = "WHERE item_id IN (\n  :item_id\n)\n"

        self.assertEqual(TrellisIndentRule().fix(content, "generic.sql", {}), content)

    def test_mismatched_directives_are_reported_without_a_fix(self):
        content = """SELECT item_id FROM sample_table
-- trellis: if active_only
WHERE retired_at IS NULL
-- trellis: endchoose
"""
        rule = TrellisDirectivesRule()

        violations = rule.check(content, "generic.sql", {})

        self.assertTrue(any("no matching choose" in violation.message for violation in violations))
        self.assertTrue(any("Unclosed if" in violation.message for violation in violations))
        self.assertEqual(rule.fix(content, "generic.sql", {}), content)

    def test_template_detection_limits_fixes_to_declared_safe_rules(self):
        content = """select item_id
    ,item_name
from sample_table
-- trellis: if active_only
where retired_at is null
-- trellis: endif
"""
        config = Config()
        config.fix = True

        result = process_document(config, content, "generic.sql", "sql")

        self.assertIn("SELECT item_id, item_name", result.content)
        self.assertIn("FROM sample_table", result.content)
        self.assertIn("IR-column-layout", result.rules_fixed)
        self.assertNotIn("IR-comma-style", result.rules_fixed)

    def test_commit_profile_standardizes_postgresql_cast_target_case(self):
        content = (
            "select generate_series(:start::timestamp with time zone, :end::timestamp) as outage_hour,\n"
            "hourly.customers_out::bigint from hourly;\n"
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        result = process_document(config, content, "audit_county_hours.sql", "sql")

        self.assertEqual(
            result.content,
            "SELECT generate_series(:start::TIMESTAMP WITH TIME ZONE, :end::TIMESTAMP) AS outage_hour, "
            "hourly.customers_out::BIGINT FROM hourly;\n",
        )
        self.assertEqual(result.diagnostics, [])
        self.assertIn("IR-datatype-case", result.rules_fixed)

    def test_processing_releases_the_document_token_cache(self):
        from mir.rules.sql.sql_utils import _tokenize_sql_impl

        _tokenize_sql_impl.cache_clear()
        config = Config()
        process_document(config, "SELECT item_id FROM sample_item;", "generic.sql", "sql")

        self.assertEqual(_tokenize_sql_impl.cache_info().currsize, 0)

    def test_changed_directive_expands_through_its_block(self):
        content = """SELECT item_id
FROM sample_table
-- trellis: if active_only
WHERE retired_at IS NULL
-- trellis: endif
;
SELECT audit_id FROM audit_table;
"""

        selection = expand_selection(content, "sql", {3})

        self.assertTrue(set(range(1, 7)).issubset(selection.allowed))
        self.assertNotIn(7, selection.allowed)

    def test_changed_directive_formats_its_full_parenthesized_block(self):
        content = (
            "SELECT item_id\n"
            "FROM sample_item\n"
            "-- trellis: if item_ids\n"
            "WHERE\n"
            "    item_id IN (\n"
            "-- trellis: for item in item_ids separator=\",\"\n"
            "  :item\n"
            "-- trellis: endfor\n"
            ")\n"
            "-- trellis: endif\n"
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        selection = expand_selection(content, "sql", {3})
        result = process_document(config, content, "generic.sql", "sql", selection)

        self.assertIn("        :item\n", result.content)
        self.assertIn("    )\n", result.content)
        self.assertIn("-- trellis: if item_ids\n", result.content)
        self.assertIn("        -- trellis: for item in item_ids separator=\",\"\n", result.content)
        self.assertEqual(trellis_directive_signature(content), trellis_directive_signature(result.content))

    def test_programming_style_nested_blocks_converge(self):
        content = (
            "SELECT item_id, item_name\n"
            "FROM sample_item\n"
            "WHERE\n"
            "    TRUE\n"
            "    -- trellis: if item_ids\n"
            "    AND item_id IN (\n"
            "        -- trellis: for item in item_ids separator=\",\"\n"
            "        :item\n"
            "        -- trellis: endfor\n"
            "    )\n"
            "    -- trellis: endif\n"
            "-- trellis: choose order\n"
            "-- trellis: when \"name\"\n"
            "ORDER BY item_name\n"
            "-- trellis: otherwise\n"
            "ORDER BY item_id\n"
            "-- trellis: endchoose\n"
        )
        expected = (
            "SELECT item_id, item_name\n"
            "FROM sample_item\n"
            "WHERE\n"
            "    TRUE\n"
            "    -- trellis: if item_ids\n"
            "        AND item_id IN (\n"
            "            -- trellis: for item in item_ids separator=\",\"\n"
            "                :item\n"
            "            -- trellis: endfor\n"
            "        )\n"
            "    -- trellis: endif\n"
            "-- trellis: choose order\n"
            "    -- trellis: when \"name\"\n"
            "        ORDER BY item_name\n"
            "    -- trellis: otherwise\n"
            "        ORDER BY item_id\n"
            "-- trellis: endchoose\n"
        )
        config = Config()
        config.profile = "commit"
        config.fix = True

        result = process_document(config, content, "generic.sql", "sql")

        self.assertEqual(result.content, expected)
        self.assertEqual(result.diagnostics, [])
        self.assertEqual(result.errors, 0)
        second = process_document(config, result.content, "generic.sql", "sql")
        self.assertEqual(second.content, expected)
        self.assertEqual(second.diagnostics, [])


if __name__ == "__main__":
    unittest.main()
