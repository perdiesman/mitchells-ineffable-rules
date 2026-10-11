"""Syntax-aware Java layout rules."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from mir.engine.rule_interface import BaseRule, RuleCase, Violation
from mir.rules.java.java_utils import (
    JavaEdit,
    apply_java_edits,
    comment_nodes,
    edit_is_authorized,
    nodes_of_type,
    parse_java,
    span_is_authorized,
    walk,
)


CONTAINER_TYPES = {
    "class_body",
    "interface_body",
    "enum_body",
    "annotation_type_body",
    "block",
    "switch_block",
}
CONTINUATION_TYPES = {
    "argument_list",
    "formal_parameters",
    "record_header",
    "throws",
    "super_interfaces",
    "superclass",
    "interfaces",
    "permits",
}
STATEMENT_TYPES = {
    "expression_statement",
    "local_variable_declaration",
    "return_statement",
    "throw_statement",
    "break_statement",
    "continue_statement",
    "yield_statement",
    "assert_statement",
}
CONTROL_KEYWORDS = {"if", "for", "while", "switch", "catch", "synchronized", "try"}
BINARY_OPERATORS = {
    "=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", ">>=", "<<=", ">>>=",
    "+", "-", "*", "/", "%", "==", "!=", "<", ">", "<=", ">=", "&&", "||", "&", "|", "^",
    "<<", ">>", ">>>", "?", ":", "->",
}


def _line_violation(rule: BaseRule, content: str, line: int, message: str, fixable: bool = True) -> Violation:
    lines = content.splitlines()
    return Violation(
        rule.rule_id,
        line,
        message,
        [lines[line - 1]] if 0 < line <= len(lines) else [],
        fixable,
    )


def _leaf_nodes(document) -> list:
    return [
        node for node in walk(document.root)
        if not node.child_count and node.type not in {"line_comment", "block_comment"}
    ]


def _line_first_nodes(document) -> dict[int, object]:
    first = {}
    for node in walk(document.root):
        if node.child_count:
            continue
        row = node.start_point.row
        if row not in first or node.start_byte < first[row].start_byte:
            first[row] = node
    for node in comment_nodes(document):
        row = node.start_point.row
        if row not in first or node.start_byte < first[row].start_byte:
            first[row] = node
    return first


def _expected_depth(node, row: int) -> int:
    depth = 0
    continuation = False
    switch_group = False
    current = node.parent
    while current is not None:
        if current.type in CONTAINER_TYPES:
            if current.start_point.row < row < current.end_point.row:
                depth += 1
            elif current.start_point.row < row == current.end_point.row:
                # Closing delimiters align with the owner of the container.
                pass
        if current.type in CONTINUATION_TYPES and current.start_point.row < row < current.end_point.row:
            continuation = True
        if current.type == "switch_block_statement_group":
            switch_group = True
        current = current.parent
    if switch_group and node.type not in {"case", "default"}:
        depth += 1
    if continuation:
        depth += 1
    return max(0, depth)


class JavaIndentRule(BaseRule):
    rule_id = "IR-indent"
    description = "Indent Java blocks and continuations with configurable four-space levels."
    category = "whitespace/layout"
    is_fixable = "yes"
    commit_profile = True
    default_config = {"indent_size": 4, "continuation_indent": 4}
    config_options = {
        "indent_size": {"default": 4, "description": "Spaces per Java block level."},
        "continuation_indent": {"default": 4, "description": "Additional spaces for wrapped constructs."},
    }
    cases = [
        RuleCase(
            "nested block",
            "class Sample {\n  void execute() {\n      if (ready) {\n       run();\n      }\n  }\n}\n",
            "fixed",
            "class Sample {\n    void execute() {\n        if (ready) {\n            run();\n        }\n    }\n}\n",
        ),
        RuleCase(
            "multiline arguments",
            "class Sample {\n    void execute() {\n        publish(\n          first,\n          second\n        );\n    }\n}\n",
            "fixed",
            "class Sample {\n    void execute() {\n        publish(\n            first,\n            second\n        );\n    }\n}\n",
        ),
    ]

    def _fixed(self, content: str, rule_config: Dict[str, Any]) -> str:
        document = parse_java(content)
        first = _line_first_nodes(document)
        size = int(rule_config.get("indent_size", 4))
        protected_rows = set()
        for node in nodes_of_type(document, "text_block"):
            protected_rows.update(range(node.start_point.row + 1, node.end_point.row))
        lines = content.splitlines(keepends=True)
        for row, node in first.items():
            if row in protected_rows or row >= len(lines):
                continue
            raw = lines[row]
            ending = "\r\n" if raw.endswith("\r\n") else ("\n" if raw.endswith("\n") else "")
            body = raw[:-len(ending)] if ending else raw
            if not body.strip():
                continue
            expected = " " * (_expected_depth(node, row) * size)
            lines[row] = expected + body.lstrip(" \t") + ending
        return "".join(lines)

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        fixed = self._fixed(content, rule_config)
        if fixed == content:
            return []
        original = content.splitlines()
        changed = fixed.splitlines()
        return [
            _line_violation(self, content, index, "Use canonical Java indentation.")
            for index, (left, right) in enumerate(zip(original, changed), start=1)
            if left != right
        ]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return self._fixed(content, rule_config)


class JavaSpacingRule(BaseRule):
    rule_id = "IR-spacing"
    description = "Use canonical spaces around Java operators, separators, and control parentheses."
    category = "whitespace/layout"
    is_fixable = "yes"
    commit_profile = True
    cases = [
        RuleCase(
            "control and operator spacing",
            "class Sample {\n    boolean test(int first,int second) {\n        if(first==second){ return true; }\n        return false;\n    }\n}\n",
            "fixed",
            "class Sample {\n    boolean test(int first, int second) {\n        if (first == second) { return true; }\n        return false;\n    }\n}\n",
        ),
        RuleCase("method invocation", "class Sample { void run() { call(first, second); } }\n", "accepted"),
    ]

    def _edits(self, content: str) -> List[JavaEdit]:
        document = parse_java(content)
        leaves = _leaf_nodes(document)
        comments = comment_nodes(document)
        edits = []
        for left, right in zip(leaves, leaves[1:]):
            if left.end_byte > right.start_byte:
                continue
            gap = document.source[left.end_byte:right.start_byte].decode()
            if "\n" in gap or any(left.end_byte <= c.start_byte < right.start_byte for c in comments):
                continue
            left_text = document.text(left)
            right_text = document.text(right)
            desired: Optional[str] = None
            if right_text == "(" and left_text in CONTROL_KEYWORDS:
                desired = " "
            elif right_text == "(" and left.type in {"identifier", "type_identifier"}:
                desired = ""
            elif left_text == ",":
                desired = " "
            elif left_text in BINARY_OPERATORS or right_text in BINARY_OPERATORS:
                if left_text not in {"!", "~", "++", "--"} and right_text not in {"++", "--"}:
                    desired = " "
            elif right_text == "{" and right.parent and right.parent.type not in {"array_initializer", "annotation_argument_list"}:
                desired = " "
            if desired is not None and gap != desired:
                edits.append(JavaEdit(left.end_byte, right.start_byte, desired))
        return edits

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        return [
            _line_violation(self, content, parse_java(content).source[:edit.start].count(b"\n") + 1, "Use canonical Java spacing.")
            for edit in self._edits(content)
        ]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return apply_java_edits(content, self._edits(content))


class BraceLayoutRule(BaseRule):
    rule_id = "IR-brace-layout"
    description = "Use K&R brace layout, multiline nonempty blocks, and joined else/catch/finally clauses."
    category = "whitespace/layout"
    is_fixable = "yes"
    commit_profile = True
    default_config = {"indent_size": 4}
    config_options = {
        "indent_size": {"default": 4, "description": "Spaces inside a nonempty block."}
    }
    cases = [
        RuleCase(
            "control block layout",
            "class Sample\n{\n    void run()\n    {\n        if (ready) { execute(); }\n        else { recover(); }\n    }\n}\n",
            "fixed",
            "class Sample {\n    void run() {\n        if (ready) {\n            execute();\n        } else {\n            recover();\n        }\n    }\n}\n",
        ),
        RuleCase("empty block", "class Sample {\n    void run() {}\n}\n", "accepted"),
    ]

    def _edits(self, content: str, config: Dict[str, Any]) -> List[JavaEdit]:
        document = parse_java(content)
        leaves = _leaf_nodes(document)
        size = int(config.get("indent_size", 4))
        edits = []
        for index, node in enumerate(leaves):
            text = document.text(node)
            if text == "{" and node.parent and node.parent.type in CONTAINER_TYPES:
                previous = leaves[index - 1] if index else None
                following = leaves[index + 1] if index + 1 < len(leaves) else None
                if previous and previous.end_byte <= node.start_byte:
                    gap = document.source[previous.end_byte:node.start_byte].decode()
                    if "\n" in gap and not any(
                        previous.end_byte <= comment.start_byte < node.start_byte
                        for comment in comment_nodes(document)
                    ):
                        edits.append(JavaEdit(previous.end_byte, node.start_byte, " "))
                if following and document.text(following) != "}" and following.start_point.row == node.start_point.row:
                    base = node.start_point.column - len(
                        document.content.splitlines()[node.start_point.row][:node.start_point.column].lstrip(" ")
                    )
                    edits.append(JavaEdit(node.end_byte, following.start_byte, "\n" + " " * (base + size)))
            elif text == "}" and index:
                previous = leaves[index - 1]
                if previous.start_point.row == node.start_point.row and document.text(previous) != "{":
                    line = document.content.splitlines()[node.start_point.row]
                    base = len(line) - len(line.lstrip(" "))
                    edits.append(JavaEdit(previous.end_byte, node.start_byte, "\n" + " " * base))
                following = leaves[index + 1] if index + 1 < len(leaves) else None
                if following and document.text(following) in {"else", "catch", "finally"}:
                    gap = document.source[node.end_byte:following.start_byte].decode()
                    if gap != " ":
                        edits.append(JavaEdit(node.end_byte, following.start_byte, " "))
        # Several braces may share the same gap in malformed input; keep the first deterministic edit.
        unique = {}
        for edit in edits:
            unique[(edit.start, edit.end)] = edit
        return [
            edit for edit in unique.values()
            if span_is_authorized(document, edit.start, edit.end, config)
        ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        return [
            _line_violation(self, content, document.source[:edit.start].count(b"\n") + 1, "Use canonical brace layout.")
            for edit in self._edits(content, rule_config)
        ]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return apply_java_edits(content, self._edits(content, rule_config))


LIST_NODE_TYPES = {
    "argument_list",
    "formal_parameters",
    "record_header",
    "annotation_argument_list",
}


class JavaListLayoutRule(BaseRule):
    rule_id = "IR-argument-layout"
    description = "Keep fitting Java argument and parameter lists compact; otherwise place each item on its own line."
    category = "methods"
    is_fixable = "yes"
    commit_profile = True
    default_config = {"max_length": 120, "indent_size": 4, "compact_if_fits": True}
    config_options = {
        "max_length": {"default": 120, "description": "Maximum compact line length."},
        "indent_size": {"default": 4, "description": "Continuation indentation."},
        "compact_if_fits": {"default": True, "description": "Collapse simple fitting lists."},
    }
    node_types = {"argument_list", "annotation_argument_list"}
    cases = [
        RuleCase(
            "compact fitting call",
            "class Sample {\n    void run() {\n        publish(\n            first,\n            second\n        );\n    }\n}\n",
            "fixed",
            "class Sample {\n    void run() {\n        publish(first, second);\n    }\n}\n",
        ),
        RuleCase(
            "configured short width",
            "class Sample { void publish(String first, String second, String third) {} }\n",
            "accepted",
        ),
    ]

    @staticmethod
    def _contains_comment(node) -> bool:
        return any(child.type in {"line_comment", "block_comment"} for child in walk(node))

    def _replacement(self, document, node, config: Dict[str, Any]) -> Optional[str]:
        children = list(node.named_children)
        if not children or self._contains_comment(node):
            return None
        values = [document.text(child).strip() for child in children]
        if any("\n" in value for value in values):
            return None
        compact = "(" + ", ".join(values) + ")"
        line_prefix = document.content.splitlines()[node.start_point.row][:node.start_point.column]
        maximum = int(config.get("max_length", 120))
        original = document.text(node)
        if config.get("compact_if_fits", True) and len(line_prefix) + len(compact) <= maximum:
            return compact if original != compact else None
        if "\n" not in original and len(line_prefix) + len(compact) <= maximum:
            return None
        base = len(line_prefix) - len(line_prefix.lstrip(" "))
        size = int(config.get("indent_size", 4))
        indent = " " * (base + size)
        close_indent = " " * base
        return "(\n" + ",\n".join(indent + value for value in values) + "\n" + close_indent + ")"

    def _edits(self, content: str, config: Dict[str, Any]) -> List[JavaEdit]:
        document = parse_java(content)
        candidates = [node for node in walk(document.root) if node.type in self.node_types]
        edits = []
        claimed = []
        # Prefer inner lists so nested calls do not receive overlapping edits.
        for node in sorted(candidates, key=lambda item: item.end_byte - item.start_byte):
            if any(not (node.end_byte <= start or node.start_byte >= end) for start, end in claimed):
                continue
            replacement = self._replacement(document, node, config)
            if replacement is not None and edit_is_authorized(node, config):
                edits.append(JavaEdit(node.start_byte, node.end_byte, replacement))
                claimed.append((node.start_byte, node.end_byte))
        return edits

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        return [
            _line_violation(self, content, document.source[:edit.start].count(b"\n") + 1, "Use canonical list layout.")
            for edit in self._edits(content, rule_config)
        ]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return apply_java_edits(content, self._edits(content, rule_config))


class ParameterLayoutRule(JavaListLayoutRule):
    rule_id = "IR-parameter-layout"
    description = "Keep fitting method, constructor, lambda, and record parameters compact; otherwise use one parameter per line."
    category = "methods"
    node_types = {"formal_parameters", "record_header", "inferred_parameters"}
    cases = [
        RuleCase(
            "compact fitting parameters",
            "class Sample {\n    void publish(\n        String first,\n        String second\n    ) {}\n}\n",
            "fixed",
            "class Sample {\n    void publish(String first, String second) {}\n}\n",
        ),
        RuleCase("compact record header", "record Sample(String name, int count) {}\n", "accepted"),
    ]


class ChainLayoutRule(BaseRule):
    rule_id = "IR-chain-layout"
    description = "Keep fitting method chains compact; otherwise align each chained call one continuation level in."
    category = "expressions"
    is_fixable = "yes"
    commit_profile = True
    default_config = {"max_length": 120, "indent_size": 4, "compact_if_fits": True}
    config_options = {
        "max_length": {"default": 120, "description": "Maximum compact chain line length."},
        "indent_size": {"default": 4, "description": "Chained-call continuation indentation."},
        "compact_if_fits": {"default": True, "description": "Collapse fitting chains."},
    }
    cases = [
        RuleCase(
            "compact chain",
            "class Sample {\n    void run() {\n        service\n            .prepare()\n            .execute();\n    }\n}\n",
            "fixed",
            "class Sample {\n    void run() {\n        service.prepare().execute();\n    }\n}\n",
        ),
        RuleCase("short chain", "class Sample { void run() { service.prepare().execute(); } }\n", "accepted"),
    ]

    def _parts(self, document, node) -> Optional[tuple[str, list[str]]]:
        segments = []
        current = node
        while current is not None and current.type == "method_invocation":
            name = current.child_by_field_name("name")
            arguments = current.child_by_field_name("arguments")
            object_node = current.child_by_field_name("object")
            if name is None or arguments is None or object_node is None:
                return None
            segments.append("." + document.text(name) + document.text(arguments))
            current = object_node
        if current is None:
            return None
        segments.reverse()
        return document.text(current), segments

    def _edits(self, content: str, config: Dict[str, Any]) -> List[JavaEdit]:
        document = parse_java(content)
        edits = []
        maximum = int(config.get("max_length", 120))
        size = int(config.get("indent_size", 4))
        for node in nodes_of_type(document, "method_invocation"):
            parent = node.parent
            if parent and parent.type == "method_invocation" and parent.child_by_field_name("object") == node:
                continue
            parts = self._parts(document, node)
            if not parts or len(parts[1]) < 2 or any(
                child.type in {"line_comment", "block_comment", "text_block"} for child in walk(node)
            ):
                continue
            base, segments = parts
            compact = base + "".join(segments)
            prefix = document.content.splitlines()[node.start_point.row][:node.start_point.column]
            original = document.text(node)
            if config.get("compact_if_fits", True) and len(prefix) + len(compact) <= maximum:
                replacement = compact
            elif len(prefix) + len(compact) > maximum:
                base_indent = len(prefix) - len(prefix.lstrip(" "))
                indent = " " * (base_indent + size)
                replacement = base + "\n" + "\n".join(indent + segment for segment in segments)
            else:
                continue
            if replacement != original and edit_is_authorized(node, config):
                edits.append(JavaEdit(node.start_byte, node.end_byte, replacement))
        return edits

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        return [
            _line_violation(self, content, document.source[:edit.start].count(b"\n") + 1, "Use canonical chained-call layout.")
            for edit in self._edits(content, rule_config)
        ]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return apply_java_edits(content, self._edits(content, rule_config))


class ExpressionLayoutRule(BaseRule):
    rule_id = "IR-expression-layout"
    description = "Keep fitting binary expressions compact; align wrapped operators at one continuation level."
    category = "expressions"
    is_fixable = "yes"
    commit_profile = True
    default_config = {"max_length": 120, "indent_size": 4, "compact_if_fits": True}
    config_options = {
        "max_length": {"default": 120, "description": "Maximum compact expression line length."},
        "indent_size": {"default": 4, "description": "Expression continuation indentation."},
        "compact_if_fits": {"default": True, "description": "Collapse fitting expressions."},
    }
    cases = [
        RuleCase(
            "parallel conditions",
            "class Sample {\n    boolean ready() {\n        return first\n                && second\n                    && third;\n    }\n}\n",
            "fixed",
            "class Sample {\n    boolean ready() {\n        return first && second && third;\n    }\n}\n",
        ),
        RuleCase("compact expression", "class Sample { boolean ready() { return first && second; } }\n", "accepted"),
    ]

    def _flatten(self, document, node) -> tuple[list[str], list[str]]:
        if node.type != "binary_expression":
            return [document.text(node).strip()], []
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        operator = node.child_by_field_name("operator")
        if left is None or right is None:
            return [document.text(node).strip()], []
        operator_text = document.text(operator) if operator is not None else next(
            (document.text(child) for child in node.children if not child.is_named), ""
        )
        left_values, left_ops = self._flatten(document, left)
        right_values, right_ops = self._flatten(document, right)
        return left_values + right_values, left_ops + [operator_text] + right_ops

    def _edits(self, content: str, config: Dict[str, Any]) -> List[JavaEdit]:
        document = parse_java(content)
        maximum = int(config.get("max_length", 120))
        size = int(config.get("indent_size", 4))
        edits = []
        for node in nodes_of_type(document, "binary_expression"):
            if node.parent and node.parent.type == "binary_expression":
                continue
            if any(child.type in {"line_comment", "block_comment", "text_block"} for child in walk(node)):
                continue
            values, operators = self._flatten(document, node)
            if len(values) < 2 or len(operators) != len(values) - 1:
                continue
            compact = values[0] + "".join(f" {op} {value}" for op, value in zip(operators, values[1:]))
            prefix = document.content.splitlines()[node.start_point.row][:node.start_point.column]
            original = document.text(node)
            if config.get("compact_if_fits", True) and len(prefix) + len(compact) <= maximum:
                replacement = compact
            elif len(prefix) + len(compact) > maximum:
                base_indent = len(prefix) - len(prefix.lstrip(" "))
                indent = " " * (base_indent + size)
                replacement = values[0] + "".join(
                    f"\n{indent}{op} {value}" for op, value in zip(operators, values[1:])
                )
            else:
                continue
            if replacement != original and edit_is_authorized(node, config):
                edits.append(JavaEdit(node.start_byte, node.end_byte, replacement))
        return edits

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        return [
            _line_violation(self, content, document.source[:edit.start].count(b"\n") + 1, "Use canonical expression layout.")
            for edit in self._edits(content, rule_config)
        ]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return apply_java_edits(content, self._edits(content, rule_config))


class OneStatementLineRule(BaseRule):
    rule_id = "IR-one-statement-line"
    description = "Place each Java statement on its own line."
    category = "whitespace/layout"
    is_fixable = "yes"
    commit_profile = True
    cases = [
        RuleCase(
            "two statements",
            "class Sample {\n    void run() {\n        prepare(); execute();\n    }\n}\n",
            "fixed",
            "class Sample {\n    void run() {\n        prepare();\n        execute();\n    }\n}\n",
        ),
        RuleCase("separate statements", "class Sample { void run() {\n    prepare();\n    execute();\n} }\n", "accepted"),
    ]

    def _edits(self, content: str) -> List[JavaEdit]:
        document = parse_java(content)
        edits = []
        for parent in walk(document.root):
            statements = [child for child in parent.named_children if child.type in STATEMENT_TYPES]
            for left, right in zip(statements, statements[1:]):
                if left.end_point.row != right.start_point.row:
                    continue
                indent = " " * left.start_point.column
                edits.append(JavaEdit(left.end_byte, right.start_byte, "\n" + indent))
        return edits

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        return [
            _line_violation(self, content, document.source[:edit.start].count(b"\n") + 1, "Place each statement on its own line.")
            for edit in self._edits(content)
        ]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return apply_java_edits(content, self._edits(content))
