import unittest

from mir.engine.config import Config
from mir.engine.runner import process_document
from mir.engine.selection import expand_selection
from mir.rules.sql.trellis_directives import TrellisDirectivesRule
from mir.rules.sql.trellis_utils import has_trellis_syntax


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


if __name__ == "__main__":
    unittest.main()
