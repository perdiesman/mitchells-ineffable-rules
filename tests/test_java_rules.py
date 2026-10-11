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
from mir.rules.java.java_utils import generated_mode, parse_java, protected_java_signature


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


if __name__ == "__main__":
    unittest.main()
