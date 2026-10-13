import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mir.engine.config import Config
from mir.engine.disabler import get_disabled_rules_map
from mir.engine.runner import process_document
from mir.engine.selection import expand_selection
from mir.engine.rules_loader import load_rules_for_language
from mir.rules.java.java_utils import generated_mode, parse_java, protected_java_signature
from mir.rules.java.advisory_rules import OneTopLevelTypeRule


class TestJavaFoundation(unittest.TestCase):
    def test_parser_supports_modern_syntax(self):
        source = (
            "sealed interface Result permits Success {}\n"
            "record Success(String value) implements Result {}\n"
        )
        self.assertFalse(parse_java(source).root.has_error)

    def test_suppression_ignores_directives_inside_text_blocks(self):
        source = (
            "class Sample {\n"
            "    String value = \"\"\"\n"
            "        // IR-all\n"
            "        \"\"\";\n"
            "    // IR-whitespace\n"
            "    int count;\n"
            "}\n"
        )
        disabled = get_disabled_rules_map(source, "Sample.java")
        self.assertEqual(disabled.get("IR-all", set()), set())
        self.assertIn(6, disabled["IR-whitespace"])

    def test_java_selection_expands_to_member(self):
        source = (
            "class Sample {\n"
            "    void execute() {\n"
            "        first();\n"
            "        second();\n"
            "    }\n"
            "}\n"
        )
        selection = expand_selection(source, "java", {3})
        self.assertEqual(selection.allowed, frozenset({2, 3, 4, 5}))

    def test_generated_source_modes(self):
        source = "// Generated source. DO NOT EDIT.\nclass Sample {}\n"
        self.assertEqual(generated_mode("src/Sample.java", source, {}), "skip")
        self.assertEqual(generated_mode("src/main/java/sample/generated/Sample.java", "class Sample {}\n", {}), "skip")
        config = {"generated": {"mode": "check"}}
        self.assertEqual(generated_mode("src/Sample.java", source, config), "check")

    def test_commit_formatter_preserves_java_tokens(self):
        source = "class Sample {\n\tint value;   \n}\n"
        config = Config()
        config.fix = True
        config.profile = "commit"
        result = process_document(config, source, "Sample.java", "java")
        self.assertEqual(result.content, "class Sample {\n    int value;\n}\n")
        self.assertEqual(
            protected_java_signature(result.content),
            protected_java_signature(source),
        )

    def test_trailing_space_after_literal_is_not_treated_as_literal_content(self):
        source = 'class Sample {\n    String value = "text";   \n}\n'
        config = Config()
        config.fix = True
        config.profile = "commit"
        result = process_document(config, source, "Sample.java", "java")
        self.assertEqual(result.content, 'class Sample {\n    String value = "text";\n}\n')

    def test_generated_source_is_skipped_by_runner(self):
        source = "// Generated source. DO NOT EDIT.\nclass Sample {   \n}\n"
        config = Config()
        config.fix = True
        result = process_document(config, source, "Sample.java", "java")
        self.assertEqual(result.content, source)
        self.assertEqual(result.errors, 0)

    def test_commit_profile_formats_generic_java(self):
        source = (
            "package sample.app;\n"
            "import sample.shared.Value;\n"
            "import java.util.List;\n"
            "class Sample\n"
            "{\n"
            "  void run(int first,int second)\n"
            "  {\n"
            "    if(first==second){ prepare(); execute(); }\n"
            "  }\n"
            "}\n"
        )
        expected = (
            "package sample.app;\n\n"
            "import java.util.List;\n\n"
            "import sample.shared.Value;\n\n"
            "class Sample {\n"
            "    void run(int first, int second) {\n"
            "        if (first == second) {\n"
            "            prepare();\n"
            "            execute();\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        config = Config()
        config.fix = True
        config.profile = "commit"
        result = process_document(config, source, "Sample.java", "java")
        self.assertEqual(result.content, expected)
        self.assertEqual(result.errors, 0)
        second = process_document(config, result.content, "Sample.java", "java")
        self.assertEqual(second.content, expected)

    def test_long_parameter_annotations_converge_with_annotation_arguments(self):
        source = (
            "class Sample {\n"
            "    void publish(\n"
            "        @OptionalValue @RequestValue(value = \"start\") "
            "@Converted(iso = Conversion.ISO.DATE_TIME) OffsetDateTime startTime,\n"
            "        @OptionalValue @RequestValue(value = \"end\") "
            "@Converted(iso = Conversion.ISO.DATE_TIME) OffsetDateTime endTime\n"
            "    ) {}\n"
            "}\n"
        )
        config = Config()
        config.fix = True
        config.profile = "commit"

        result = process_document(config, source, "Sample.java", "java")

        self.assertEqual(result.diagnostics, [])
        self.assertIn(
            "        @OptionalValue\n"
            "        @RequestValue(value = \"start\")\n"
            "        @Converted(iso = Conversion.ISO.DATE_TIME)\n"
            "        OffsetDateTime startTime,",
            result.content,
        )
        second = process_document(config, result.content, "Sample.java", "java")
        self.assertEqual(second.content, result.content)
        self.assertEqual(second.diagnostics, [])

    def test_parenthesized_ternary_and_binary_chain_layouts_converge(self):
        source = (
            "class Sample {\n"
            "    Date choose(Date endDate, Date fallbackDate) {\n"
            "        Date selectedDate = (endDate == null ? Date.from(fallbackDate.toInstant().plus(24, ChronoUnit.HOURS)) : Date.from(endDate.toInstant()));\n"
            "        return selectedDate;\n"
            "    }\n"
            "    String describe(Cache primaryCache, Cache secondaryCache) {\n"
            "        return \"Primary entries: \" + primaryCache.keys().count() + \", secondary entries: \" + secondaryCache.keys().count();\n"
            "    }\n"
            "}\n"
        )
        config = Config()
        config.fix = True
        config.profile = "commit"

        result = process_document(config, source, "Sample.java", "java")

        self.assertEqual(result.diagnostics, [])
        self.assertIn(
            "        Date selectedDate =\n"
            "            (endDate == null\n"
            "                ? Date.from(fallbackDate.toInstant().plus(24, ChronoUnit.HOURS))\n"
            "                : Date.from(endDate.toInstant()));",
            result.content,
        )
        self.assertIn(
            "            + secondaryCache\n"
            "                .keys()\n"
            "                .count();",
            result.content,
        )
        second = process_document(config, result.content, "Sample.java", "java")
        self.assertEqual(second.content, result.content)
        self.assertEqual(second.diagnostics, [])

    def test_block_suppression_prevents_partial_brace_edit(self):
        source = (
            "class Sample {\n"
            "    // IR-start-brace-layout\n"
            "    void run()\n"
            "    {\n"
            "        execute();\n"
            "    }\n"
            "    // IR-end-brace-layout\n"
            "}\n"
        )
        config = Config()
        config.fix = True
        result = process_document(config, source, "Sample.java", "java")
        self.assertIn("void run()\n    {", result.content)

    def test_semantic_fix_is_opt_in_and_excluded_from_commit(self):
        source = (
            "class Sample {\n"
            "    boolean ready(boolean enabled) {\n"
            "        return enabled == true;\n"
            "    }\n"
            "}\n"
        )
        commit = Config()
        commit.fix = True
        commit.profile = "commit"
        self.assertIn("enabled == true", process_document(commit, source, "Sample.java", "java").content)

        normal = Config()
        normal.fix = True
        self.assertIn("enabled == true", process_document(normal, source, "Sample.java", "java").content)

        opted_in = Config()
        opted_in.fix = True
        opted_in.rule_configs = {"java:IR-redundant-boolean-comparison": {"semantic_fix": True}}
        result = process_document(opted_in, source, "Sample.java", "java")
        self.assertIn("return enabled;", result.content)

    def test_java_rule_examples_are_generic(self):
        forbidden = ("gov.ornl", "eaglei", "aerie", "planetsense")
        for rule in load_rules_for_language("java"):
            snippets = [case.source for case in rule.cases]
            snippets.extend(case.fixed for case in rule.cases if case.fixed)
            snippets.extend(example.get("violating", "") for example in rule.examples)
            snippets.extend(example.get("correct", "") for example in rule.examples)
            combined = "\n".join(snippets).lower()
            for value in forbidden:
                self.assertNotIn(value, combined, f"{rule.rule_id} contains compatibility-specific example text")

    def test_top_level_type_matches_real_java_filename(self):
        rule = OneTopLevelTypeRule()
        source = "class Sample {}\n"
        self.assertEqual(rule.check(source, "Sample.java", {}), [])
        self.assertEqual(len(rule.check(source, "Different.java", {})), 1)


if __name__ == "__main__":
    unittest.main()
