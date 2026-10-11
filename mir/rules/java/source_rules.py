"""Java source-file, whitespace, and import rules."""

from __future__ import annotations

from collections import defaultdict
import re
from typing import Any, Dict, List

from mir.engine.rule_interface import BaseRule, RuleCase, Violation
from mir.rules.java.java_utils import (
    comment_nodes,
    error_nodes,
    nodes_of_type,
    parse_java,
    walk,
)


def _violation(rule: BaseRule, content: str, line: int, message: str, fixable: bool) -> Violation:
    lines = content.splitlines()
    offending = [lines[line - 1]] if 0 < line <= len(lines) else []
    return Violation(rule.rule_id, line, message, offending, fixable)


def _protected_rows(content: str) -> set[int]:
    document = parse_java(content)
    rows = set()
    for node in walk(document.root):
        if node.type in {"string_literal", "character_literal", "text_block", "line_comment", "block_comment"}:
            rows.update(range(node.start_point.row, node.end_point.row + 1))
    return rows


class JavaSyntaxRule(BaseRule):
    rule_id = "IR-java-syntax"
    description = "Java source must parse without missing or erroneous syntax nodes."
    category = "general"
    is_fixable = "no"
    commit_profile = True
    cases = [
        RuleCase("valid type", "class Sample {}\n", "accepted"),
        RuleCase("missing type body", "class Sample {\n", "reported"),
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        lines = content.splitlines()
        violations = []
        seen = set()
        for node in error_nodes(parse_java(content)):
            line = node.start_point.row + 1
            if line in seen:
                continue
            seen.add(line)
            violations.append(Violation(
                self.rule_id,
                line,
                "Java syntax could not be parsed safely.",
                [lines[line - 1]] if line <= len(lines) else [],
                False,
            ))
        return violations


class WhitespaceRule(BaseRule):
    rule_id = "IR-whitespace"
    description = "Use spaces for indentation and remove trailing whitespace outside literals and comments."
    category = "whitespace/layout"
    is_fixable = "yes"
    commit_profile = True
    default_config = {"indent_size": 4}
    config_options = {
        "indent_size": {"default": 4, "description": "Spaces represented by one indentation tab."}
    }
    cases = [
        RuleCase(
            "indentation tab and trailing code space",
            "class Sample {\n\tint value;   \n}\n",
            "fixed",
            "class Sample {\n    int value;\n}\n",
        ),
        RuleCase(
            "text block whitespace",
            'class Sample {\n    String value = """\n        keep   \n        """;\n}\n',
            "accepted",
        ),
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        protected = _protected_rows(content)
        violations = []
        for index, line in enumerate(content.splitlines(), start=1):
            prefix = line[: len(line) - len(line.lstrip(" \t"))]
            if "\t" in prefix or (index - 1 not in protected and line.rstrip() != line):
                violations.append(_violation(self, content, index, "Normalize Java whitespace.", True))
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        protected = _protected_rows(content)
        size = int(rule_config.get("indent_size", 4))
        output = []
        for row, line in enumerate(content.splitlines(keepends=True)):
            ending = "\r\n" if line.endswith("\r\n") else ("\n" if line.endswith("\n") else "")
            body = line[:-len(ending)] if ending else line
            prefix = body[: len(body) - len(body.lstrip(" \t"))]
            normalized = prefix.replace("\t", " " * size) + body[len(prefix):]
            if row not in protected:
                normalized = normalized.rstrip()
            output.append(normalized + ending)
        return "".join(output)


class FinalNewlineRule(BaseRule):
    rule_id = "IR-final-newline"
    description = "Java files end with exactly one line terminator."
    category = "general"
    is_fixable = "yes"
    commit_profile = True
    cases = [
        RuleCase("missing newline", "class Sample {}", "fixed", "class Sample {}\n"),
        RuleCase("single newline", "class Sample {}\n", "accepted"),
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        if content and (not content.endswith("\n") or content.endswith("\n\n")):
            return [_violation(self, content, max(1, len(content.splitlines())), "Use one final newline.", True)]
        return []

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return content.rstrip("\r\n") + "\n" if content else content


class BlankLinesRule(BaseRule):
    rule_id = "IR-blank-lines"
    description = "Do not start a Java file with a blank line or use consecutive blank lines."
    category = "whitespace/layout"
    is_fixable = "yes"
    commit_profile = True
    cases = [
        RuleCase(
            "leading and repeated blank lines",
            "\nclass Sample {\n\n\n    int value;\n}\n",
            "fixed",
            "class Sample {\n\n    int value;\n}\n",
        ),
        RuleCase("single separator", "class Sample {\n\n    int value;\n}\n", "accepted"),
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        protected = _protected_rows(content)
        previous_blank = False
        violations = []
        for row, line in enumerate(content.splitlines(), start=1):
            blank = not line.strip()
            if row - 1 not in protected and blank and (row == 1 or previous_blank):
                violations.append(_violation(self, content, row, "Remove the extra blank line.", True))
            previous_blank = blank if row - 1 not in protected else False
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        protected = _protected_rows(content)
        output = []
        previous_blank = False
        for row, line in enumerate(content.splitlines(keepends=True)):
            blank = not line.strip()
            if row not in protected and blank and (not output or previous_blank):
                continue
            output.append(line)
            previous_blank = blank if row not in protected else False
        return "".join(output)


class JavaLineLengthRule(BaseRule):
    rule_id = "IR-line-length"
    description = "Java code should not exceed the configured line length; package, import, and text-block payload lines are exempt."
    category = "general"
    is_fixable = "no"
    # Structural wrapping rules run in the commit profile. Until every Java
    # construct has an automatic wrapper, a report-only width check must not
    # block commits after the formatter has done all work it safely can.
    commit_profile = False
    default_config = {"max_length": 120}
    config_options = {
        "max_length": {"default": 120, "description": "Maximum Java code line length."}
    }
    cases = [
        RuleCase(
            "long statement",
            "class Sample {\n    String value = createValueWithAnExcessivelyLongAndGenericMethodName(firstArgument, secondArgument, thirdArgument, fourthArgument);\n}\n",
            "reported",
        ),
        RuleCase("short statement", "class Sample {\n    int value = 1;\n}\n", "accepted"),
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        maximum = int(rule_config.get("max_length", 120))
        document = parse_java(content)
        exempt = set()
        for node in walk(document.root):
            if node.type in {"package_declaration", "import_declaration", "text_block"}:
                exempt.update(range(node.start_point.row + 1, node.end_point.row + 2))
        return [
            _violation(self, content, number, f"Line exceeds {maximum} characters.", False)
            for number, line in enumerate(content.splitlines(), start=1)
            if number not in exempt and len(line) > maximum
        ]


class SourceLayoutRule(BaseRule):
    rule_id = "IR-source-layout"
    description = "Separate package, import, and top-level type sections with one blank line."
    category = "source-structure"
    is_fixable = "sometimes"
    commit_profile = True
    cases = [
        RuleCase(
            "package and imports",
            "package sample.app;\nimport java.util.List;\nclass Sample {}\n",
            "fixed",
            "package sample.app;\n\nimport java.util.List;\n\nclass Sample {}\n",
        ),
        RuleCase(
            "canonical sections",
            "package sample.app;\n\nimport java.util.List;\n\nclass Sample {}\n",
            "accepted",
        ),
    ]

    def _fixed(self, content: str) -> str:
        document = parse_java(content)
        if comment_nodes(document):
            return content
        lines = content.splitlines()
        boundaries = []
        package = next(nodes_of_type(document, "package_declaration"), None)
        imports = list(nodes_of_type(document, "import_declaration"))
        if package and imports:
            boundaries.append((package.end_point.row + 1, imports[0].start_point.row))
        if imports:
            following = [
                child for child in document.root.named_children
                if child.start_byte >= imports[-1].end_byte and child.type != "import_declaration"
            ]
            if following:
                boundaries.append((imports[-1].end_point.row + 1, following[0].start_point.row))
        for start, end in reversed(boundaries):
            lines[start:end] = [""]
        ending = "\n" if content.endswith("\n") else ""
        return "\n".join(lines) + ending

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        fixed = self._fixed(content)
        if fixed != content:
            document = parse_java(content)
            package = next(nodes_of_type(document, "package_declaration"), None)
            line = package.end_point.row + 2 if package else 1
            return [_violation(self, content, line, "Use one blank line between source sections.", fixed != content)]
        return []

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return self._fixed(content)


class ImportOrderRule(BaseRule):
    rule_id = "IR-import-order"
    description = "Sort imports into static, platform, third-party, and project groups."
    category = "imports"
    is_fixable = "sometimes"
    commit_profile = True
    commit_semantic_rewrite = True
    default_config = {"project_prefixes": []}
    config_options = {
        "project_prefixes": {
            "default": [],
            "description": "Package prefixes placed in the project import group; the current package is inferred when empty.",
        }
    }
    cases = [
        RuleCase(
            "grouped imports",
            "package sample.app;\n\nimport sample.shared.Value;\nimport java.util.List;\nimport static java.util.Collections.emptyList;\n\nclass Sample {}\n",
            "fixed",
            "package sample.app;\n\nimport static java.util.Collections.emptyList;\n\nimport java.util.List;\n\nimport sample.shared.Value;\n\nclass Sample {}\n",
        ),
        RuleCase(
            "canonical imports",
            "package sample.app;\n\nimport java.util.List;\n\nimport sample.shared.Value;\n\nclass Sample {}\n",
            "accepted",
        ),
    ]

    def _fixed(self, content: str, rule_config: Dict[str, Any]) -> str:
        document = parse_java(content)
        imports = list(nodes_of_type(document, "import_declaration"))
        if len(imports) < 2 or comment_nodes(document):
            return content
        package = next(nodes_of_type(document, "package_declaration"), None)
        explicit = [str(value) for value in rule_config.get("project_prefixes", [])]
        if explicit:
            project_prefixes = explicit
        elif package:
            package_name = document.text(package).removeprefix("package").removesuffix(";").strip()
            project_prefixes = [".".join(package_name.split(".")[:2])]
        else:
            project_prefixes = []

        grouped = defaultdict(list)
        for node in imports:
            text = document.text(node).strip()
            name = text.removeprefix("import ").removeprefix("static ").removesuffix(";")
            if text.startswith("import static "):
                group = 0
            elif name.startswith(("java.", "javax.", "jakarta.")):
                group = 1
            elif any(name.startswith(prefix + ".") for prefix in project_prefixes):
                group = 3
            else:
                group = 2
            grouped[group].append(text)
        blocks = ["\n".join(sorted(set(grouped[group]))) for group in range(4) if grouped[group]]
        replacement = "\n\n".join(blocks)
        source = content.encode("utf-8")
        source = source[: imports[0].start_byte] + replacement.encode() + source[imports[-1].end_byte :]
        return source.decode()

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        fixed = self._fixed(content, rule_config)
        if fixed != content:
            imports = list(nodes_of_type(parse_java(content), "import_declaration"))
            return [_violation(self, content, imports[0].start_point.row + 1, "Use canonical import grouping and order.", True)]
        return []

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return self._fixed(content, rule_config)


class NoWildcardImportsRule(BaseRule):
    rule_id = "IR-no-wildcard-imports"
    description = "Use explicit imports instead of wildcard imports."
    category = "imports"
    is_fixable = "no"
    default_config = {"severity": "warning"}
    config_options = {"severity": {"default": "warning", "description": "Violation severity."}}
    cases = [
        RuleCase("wildcard import", "import sample.api.*;\nclass Sample {}\n", "reported"),
        RuleCase("explicit import", "import sample.api.Value;\nclass Sample {}\n", "accepted"),
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        return [
            _violation(self, content, node.start_point.row + 1, "Replace the wildcard import with explicit imports.", False)
            for node in nodes_of_type(document, "import_declaration")
            if document.text(node).rstrip().endswith(".*;")
        ]
