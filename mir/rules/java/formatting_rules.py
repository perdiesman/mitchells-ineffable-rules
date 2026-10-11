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
    "constructor_body",
    "switch_block",
}
CONTINUATION_TYPES = {
    "argument_list",
    "annotation_argument_list",
    "formal_parameters",
    "record_header",
    "array_initializer",
    "element_value_array_initializer",
    "resource_specification",
    "throws",
    "super_interfaces",
    "superclass",
    "interfaces",
    "permits",
    "method_invocation",
    "binary_expression",
    "ternary_expression",
    "parenthesized_expression",
    "assignment_expression",
    "variable_declarator",
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
    protected = {"line_comment", "block_comment", "string_literal", "character_literal", "text_block"}
    nodes = document.nodes
    protected_ranges = sorted(
        (node.start_byte, node.end_byte)
        for node in nodes
        if node.type in protected
    )
    leaves = []
    range_index = 0
    for node in nodes:
        if node.child_count or node.type in protected:
            continue
        while range_index < len(protected_ranges) and protected_ranges[range_index][1] <= node.start_byte:
            range_index += 1
        if (
            range_index < len(protected_ranges)
            and protected_ranges[range_index][0] <= node.start_byte < protected_ranges[range_index][1]
        ):
            continue
        leaves.append(node)
    return leaves


def _ancestors(node):
    while node is not None:
        yield node
        node = node.parent


def _terminal_suffix(document, node) -> str:
    line = document.content.splitlines()[node.end_point.row]
    suffix = line[node.end_point.column:].rstrip()
    compact = "".join(suffix.split())
    return suffix if compact and all(character in ")]},;{" for character in compact) else ""


def _line_first_nodes(document) -> dict[int, object]:
    first = {}
    for node in document.nodes:
        if node.child_count and node.type not in {"line_comment", "block_comment"}:
            continue
        row = node.start_point.row
        if row not in first or node.start_byte < first[row].start_byte:
            first[row] = node
    return first


def _expected_depth(node, row: int) -> int:
    depth = 0
    continuations = set()
    list_depth = 0
    within_list = False
    list_start_rows = []
    switch_group_depth = 0
    switch_rule_depth = 0
    ternary_depth = 0
    parenthesized_depth = 0
    within_switch_expression = False
    current = node.parent
    while current is not None:
        if current.type == "switch_expression":
            within_switch_expression = True
        if current.type in CONTAINER_TYPES:
            if current.start_point.row < row < current.end_point.row:
                depth += 1
            elif current.start_point.row < row == current.end_point.row:
                # Closing delimiters align with the owner of the container.
                pass
        if current.type in CONTINUATION_TYPES:
            is_list = current.type in {
                "argument_list",
                "annotation_argument_list",
                "formal_parameters",
                "record_header",
                "array_initializer",
                "element_value_array_initializer",
                "resource_specification",
            }
            closes_current = False
            if current.type in {"method_invocation", "binary_expression", "ternary_expression"}:
                active = current.start_point.row < row <= current.end_point.row
            else:
                closes_current = (
                    node.type in {")", "]", "}"}
                    and current.type in {
                        "argument_list",
                        "annotation_argument_list",
                        "formal_parameters",
                        "record_header",
                        "array_initializer",
                        "element_value_array_initializer",
                        "resource_specification",
                    }
                    and node.end_byte == current.end_byte
                )
                active = (
                    current.start_point.row < row <= current.end_point.row
                    and not closes_current
                )
            if is_list and (active or closes_current):
                within_list = True
                list_start_rows.append(current.start_point.row)
            if active:
                if current.type == "method_invocation":
                    if node.type == ".":
                        continuations.add("chain")
                elif current.type in {"binary_expression", "ternary_expression", "parenthesized_expression"}:
                    continuations.add("expression")
                    if current.type == "ternary_expression":
                        ternary_depth += 1
                    elif current.type == "parenthesized_expression":
                        parenthesized_depth += 1
                elif current.type in {"assignment_expression", "variable_declarator"}:
                    if "chain" not in continuations and not within_switch_expression and (not within_list or any(
                        start_row > current.start_point.row
                        for start_row in list_start_rows
                    )):
                        continuations.add("expression")
                elif current.type in {
                    "argument_list",
                    "annotation_argument_list",
                    "formal_parameters",
                    "record_header",
                    "array_initializer",
                    "element_value_array_initializer",
                    "resource_specification",
                }:
                    list_depth += 1
                else:
                    continuations.add("type")
        if current.type == "switch_block_statement_group":
            switch_group_depth += 1
        elif current.type == "switch_rule":
            switch_rule_depth += 1
        current = current.parent
    depth += max(0, switch_group_depth - int(node.type in {"case", "default"}))
    depth += max(0, switch_rule_depth - int(node.type in {"case", "default"}))
    depth += max(0, ternary_depth - 1)
    depth += parenthesized_depth
    depth += len(continuations) + list_depth
    return max(0, depth)


def _wrapped_continuation_depth(node, category: str) -> int:
    """Return the canonical depth for a wrapped construct within *node*."""
    depth = 0
    continuations = set() if category == "list" else {category}
    list_depth = int(category == "list")
    list_start_rows = [node.start_point.row] if category == "list" else []
    switch_group_depth = 0
    switch_rule_depth = 0
    ternary_depth = int(node.type == "ternary_expression")
    parenthesized_depth = 0
    current = node.parent
    while current is not None:
        if current.type in CONTAINER_TYPES:
            depth += 1
        elif current.type in {"binary_expression", "ternary_expression", "parenthesized_expression"}:
            continuations.add("expression")
            if current.type == "ternary_expression":
                ternary_depth += 1
            elif current.type == "parenthesized_expression":
                parenthesized_depth += 1
        elif current.type in {"assignment_expression", "variable_declarator"}:
            if category != "chain" and (list_depth == 0 or any(
                start_row > current.start_point.row
                for start_row in list_start_rows
            )):
                continuations.add("expression")
        elif current.type in {
            "argument_list",
            "annotation_argument_list",
            "formal_parameters",
            "record_header",
            "array_initializer",
            "element_value_array_initializer",
            "resource_specification",
        }:
            list_depth += 1
            list_start_rows.append(current.start_point.row)
        elif current.type in {"throws", "super_interfaces", "superclass", "interfaces", "permits"}:
            continuations.add("type")
        if current.type == "switch_block_statement_group":
            switch_group_depth += 1
        elif current.type == "switch_rule":
            switch_rule_depth += 1
        current = current.parent
    return (
        depth
        + len(continuations)
        + list_depth
        + switch_group_depth
        + switch_rule_depth
        + max(0, ternary_depth - 1)
        + parenthesized_depth
    )


def _spaced_operator(node, text: str) -> bool:
    if text not in BINARY_OPERATORS or node.parent is None:
        return False
    if node.parent.type in {
        "binary_expression",
        "assignment_expression",
        "ternary_expression",
        "lambda_expression",
        "enhanced_for_statement",
        "catch_type",
        "type_bound",
    }:
        return True
    return False


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
        RuleCase(
            "constructor body",
            "class Sample {\n    Sample(\n        int value\n    ) {\n    this.value = value;\n    }\n    int value;\n}\n",
            "fixed",
            "class Sample {\n    Sample(\n        int value\n    ) {\n        this.value = value;\n    }\n    int value;\n}\n",
        ),
        RuleCase(
            "assignment continuation",
            "class Sample {\n    void execute() {\n        String value =\n        createValue();\n    }\n    String createValue() { return \"value\"; }\n}\n",
            "fixed",
            "class Sample {\n    void execute() {\n        String value =\n            createValue();\n    }\n    String createValue() { return \"value\"; }\n}\n",
        ),
    ]

    def _fixed(self, content: str, rule_config: Dict[str, Any]) -> str:
        document = parse_java(content)
        first = _line_first_nodes(document)
        size = int(rule_config.get("indent_size", 4))
        protected_rows = set()
        for node in document.nodes:
            if node.type == "text_block" or (
                node.type == "string_literal"
                and node.start_point.row != node.end_point.row
            ):
                protected_rows.update(range(node.start_point.row, node.end_point.row + 1))
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
        edits = []
        for left, right in zip(leaves, leaves[1:]):
            if left.end_byte > right.start_byte:
                continue
            gap = document.source[left.end_byte:right.start_byte].decode()
            if gap.strip() or "\n" in gap:
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
            elif _spaced_operator(left, left_text) or _spaced_operator(right, right_text):
                desired = " "
            elif right_text == "{" and right.parent and right.parent.type not in {
                "array_initializer",
                "element_value_array_initializer",
                "annotation_argument_list",
            }:
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
        comments = comment_nodes(document)
        size = int(config.get("indent_size", 4))
        edits = []
        for index, node in enumerate(leaves):
            text = document.text(node)
            if text == "{" and node.parent and node.parent.type in CONTAINER_TYPES:
                previous = leaves[index - 1] if index else None
                following = leaves[index + 1] if index + 1 < len(leaves) else None
                if (
                    previous
                    and document.text(previous) != "{"
                    and previous.end_byte <= node.start_byte
                ):
                    gap = document.source[previous.end_byte:node.start_byte].decode()
                    if not gap.strip() and "\n" in gap and not any(
                        previous.end_byte <= comment.start_byte < node.start_byte
                        for comment in comments
                    ):
                        edits.append(JavaEdit(previous.end_byte, node.start_byte, " "))
                if following and document.text(following) != "}" and following.start_point.row == node.start_point.row:
                    gap = document.source[node.end_byte:following.start_byte].decode()
                    if gap.strip():
                        continue
                    base = node.start_point.column - len(
                        document.content.splitlines()[node.start_point.row][:node.start_point.column].lstrip(" ")
                    )
                    edits.append(JavaEdit(node.end_byte, following.start_byte, "\n" + " " * (base + size)))
            elif (
                text == "}"
                and index
                and node.parent
                and node.parent.type in CONTAINER_TYPES
            ):
                previous = leaves[index - 1]
                if previous.start_point.row == node.start_point.row and document.text(previous) != "{":
                    gap = document.source[previous.end_byte:node.start_byte].decode()
                    if gap.strip():
                        continue
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
        return any(
            child.type in {"line_comment", "block_comment", "text_block"}
            or (
                child.type == "string_literal"
                and child.start_point.row != child.end_point.row
            )
            for child in walk(node)
        )

    def _line_suffix(self, document, node) -> str:
        return _terminal_suffix(document, node)

    def _replacement(self, document, node, config: Dict[str, Any]) -> Optional[str]:
        children = list(node.named_children)
        if not children or self._contains_comment(node):
            return None
        values = [document.text(child).strip() for child in children]
        has_multiline_value = any("\n" in value for value in values)
        compact = "(" + ", ".join(values) + ")"
        lines = document.content.splitlines()
        line_prefix = lines[node.start_point.row][:node.start_point.column]
        line_suffix = self._line_suffix(document, node)
        compact_length = len(line_prefix) + len(compact) + len(line_suffix)
        maximum = int(config.get("max_length", 120))
        original = document.text(node)
        if (
            not has_multiline_value
            and config.get("compact_if_fits", True)
            and compact_length <= maximum
        ):
            return compact if original != compact else None
        if not has_multiline_value and "\n" not in original and compact_length <= maximum:
            return None
        size = int(config.get("indent_size", 4))
        depth = _wrapped_continuation_depth(node, "list")
        indent = " " * (depth * size)
        close_indent = " " * (max(0, depth - 1) * size)
        rendered_values = []
        for child, value in zip(children, values):
            value_lines = value.splitlines()
            rendered = [indent + value_lines[0]]
            for line in value_lines[1:]:
                if not line.strip():
                    rendered.append("")
                    continue
                leading = len(line) - len(line.lstrip(" "))
                relative = max(0, leading - child.start_point.column)
                rendered.append(indent + " " * relative + line.lstrip(" "))
            rendered_values.append("\n".join(rendered))
        replacement = "(\n" + ",\n".join(rendered_values) + "\n" + close_indent + ")"
        return replacement if replacement != original else None

    def _edits(self, content: str, config: Dict[str, Any]) -> List[JavaEdit]:
        document = parse_java(content)
        candidates = [node for node in document.nodes if node.type in self.node_types]
        edits = []
        claimed = []
        # Prefer the outer list when both levels can be normalized. If an outer
        # list owns multiline content it yields no replacement, allowing its
        # inner lists to be considered independently in the same pass.
        for node in sorted(
            candidates,
            key=lambda item: item.end_byte - item.start_byte,
            reverse=True,
        ):
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

    def _line_suffix(self, document, node) -> str:
        line = document.content.splitlines()[node.end_point.row]
        return line[node.end_point.column:].rstrip()

    cases = [
        RuleCase(
            "compact fitting parameters",
            "class Sample {\n    void publish(\n        String first,\n        String second\n    ) {}\n}\n",
            "fixed",
            "class Sample {\n    void publish(String first, String second) {}\n}\n",
        ),
        RuleCase("compact record header", "record Sample(String name, int count) {}\n", "accepted"),
        RuleCase(
            "record suffix exceeds width",
            "public record SampleRecord(Integer id, Integer ownerId, String name, Integer status, Date modifiedAt, String notesValue) {}\n",
            "fixed",
            "public record SampleRecord(\n"
            "    Integer id,\n"
            "    Integer ownerId,\n"
            "    String name,\n"
            "    Integer status,\n"
            "    Date modifiedAt,\n"
            "    String notesValue\n"
            ") {}\n",
        ),
        RuleCase(
            "throws clause exceeds width",
            "class Sample {\n"
            "    private void publish(int maximumCount, int minimumCount, String categoryName, List<SampleNotification> notifications) throws Exception {}\n"
            "}\n",
            "fixed",
            "class Sample {\n"
            "    private void publish(\n"
            "        int maximumCount,\n"
            "        int minimumCount,\n"
            "        String categoryName,\n"
            "        List<SampleNotification> notifications\n"
            "    ) throws Exception {}\n"
            "}\n",
        ),
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
        RuleCase(
            "chain beginning with invocation",
            "class Sample {\n"
            "    String read() {\n"
            "        return loadExtraordinarilyDescriptiveResponse(firstArgument, secondArgument, thirdArgument, fourthArgument).result().body().asText();\n"
            "    }\n"
            "}\n",
            "fixed",
            "class Sample {\n"
            "    String read() {\n"
            "        return loadExtraordinarilyDescriptiveResponse(firstArgument, secondArgument, thirdArgument, fourthArgument)\n"
            "            .result()\n"
            "            .body()\n"
            "            .asText();\n"
            "    }\n"
            "}\n",
        ),
    ]

    def _parts(self, document, node) -> Optional[tuple[str, list[str]]]:
        segments = []
        current = node
        while current is not None and current.type == "method_invocation":
            name = current.child_by_field_name("name")
            arguments = current.child_by_field_name("arguments")
            object_node = current.child_by_field_name("object")
            if name is None or arguments is None:
                return None
            if object_node is None:
                break
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
        claimed = []
        candidates = list(nodes_of_type(document, "method_invocation"))
        for node in sorted(candidates, key=lambda item: item.end_byte - item.start_byte):
            if any(not (node.end_byte <= start or node.start_byte >= end) for start, end in claimed):
                continue
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
            suffix_length = len(_terminal_suffix(document, node))
            compact_length = len(prefix) + len(compact) + suffix_length
            original = document.text(node)
            multiline_binary_parent = any(
                ancestor.type == "binary_expression" and ancestor.start_point.row < ancestor.end_point.row
                for ancestor in _ancestors(node.parent)
            )
            if (
                config.get("compact_if_fits", True)
                and compact_length <= maximum
                and not ("\n" in original and multiline_binary_parent)
            ):
                replacement = compact
            elif compact_length > maximum:
                indent = " " * (_wrapped_continuation_depth(node, "chain") * size)
                replacement = base + "\n" + "\n".join(indent + segment for segment in segments)
            else:
                continue
            if replacement != original and edit_is_authorized(node, config):
                edits.append(JavaEdit(node.start_byte, node.end_byte, replacement))
                claimed.append((node.start_byte, node.end_byte))
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
        claimed = []
        candidates = list(nodes_of_type(document, "binary_expression"))
        for node in sorted(candidates, key=lambda item: item.end_byte - item.start_byte):
            if any(not (node.end_byte <= start or node.start_byte >= end) for start, end in claimed):
                continue
            if node.parent and node.parent.type == "binary_expression":
                continue
            if any(child.type in {"line_comment", "block_comment", "text_block"} for child in walk(node)):
                continue
            values, operators = self._flatten(document, node)
            if len(values) < 2 or len(operators) != len(values) - 1:
                continue
            compact = values[0] + "".join(f" {op} {value}" for op, value in zip(operators, values[1:]))
            prefix = document.content.splitlines()[node.start_point.row][:node.start_point.column]
            suffix_length = len(_terminal_suffix(document, node))
            original = document.text(node)
            if config.get("compact_if_fits", True) and len(prefix) + len(compact) + suffix_length <= maximum:
                replacement = compact
            elif len(prefix) + len(compact) + suffix_length > maximum:
                indent = " " * (_wrapped_continuation_depth(node, "expression") * size)
                replacement = values[0] + "".join(
                    f"\n{indent}{op} {value}" for op, value in zip(operators, values[1:])
                )
            else:
                continue
            if replacement != original and edit_is_authorized(node, config):
                edits.append(JavaEdit(node.start_byte, node.end_byte, replacement))
                claimed.append((node.start_byte, node.end_byte))
        return edits

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        return [
            _line_violation(self, content, document.source[:edit.start].count(b"\n") + 1, "Use canonical expression layout.")
            for edit in self._edits(content, rule_config)
        ]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return apply_java_edits(content, self._edits(content, rule_config))


class AssignmentLayoutRule(BaseRule):
    rule_id = "IR-assignment-layout"
    description = "Keep fitting assignments compact; otherwise place the assigned value one continuation level after the operator."
    category = "expressions"
    is_fixable = "yes"
    commit_profile = True
    default_config = {"max_length": 120, "indent_size": 4}
    config_options = {
        "max_length": {"default": 120, "description": "Maximum compact assignment line length."},
        "indent_size": {"default": 4, "description": "Assigned-value continuation indentation."},
    }
    cases = [
        RuleCase(
            "long initializer",
            "class Sample {\n"
            "    List<ExtraordinarilyDescriptiveResult> descriptiveResults = (List<ExtraordinarilyDescriptiveResult>) cache.getIfPresent(cacheKey);\n"
            "}\n",
            "fixed",
            "class Sample {\n"
            "    List<ExtraordinarilyDescriptiveResult> descriptiveResults =\n"
            "        (List<ExtraordinarilyDescriptiveResult>) cache.getIfPresent(cacheKey);\n"
            "}\n",
        ),
        RuleCase(
            "compact assignment",
            "class Sample { int count = 1; }\n",
            "accepted",
        ),
    ]

    @staticmethod
    def _operator(node):
        named = node.child_by_field_name("operator")
        if named is not None:
            return named
        return next(
            (child for child in node.children if child.type.endswith("=")),
            None,
        )

    def _edits(self, content: str, config: Dict[str, Any]) -> List[JavaEdit]:
        if "=" not in content:
            return []
        document = parse_java(content)
        lines = document.content.splitlines()
        maximum = int(config.get("max_length", 120))
        size = int(config.get("indent_size", 4))
        comments = list(nodes_of_type(document, "line_comment", "block_comment"))
        edits = []
        for node in nodes_of_type(document, "variable_declarator", "assignment_expression"):
            value = node.child_by_field_name("value") or node.child_by_field_name("right")
            operator = self._operator(node)
            if value is None or operator is None or operator.end_point.row != value.start_point.row:
                continue
            row = value.start_point.row
            if len(lines[row]) <= maximum or any(
                comment.start_point.row <= row <= comment.end_point.row for comment in comments
            ):
                continue
            gap = document.source[operator.end_byte:value.start_byte].decode()
            if gap.strip():
                continue
            indent = " " * (_wrapped_continuation_depth(node, "expression") * size)
            if span_is_authorized(document, operator.end_byte, value.start_byte, config):
                edits.append(JavaEdit(operator.end_byte, value.start_byte, "\n" + indent))
        return edits

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        return [
            _line_violation(
                self,
                content,
                document.source[:edit.start].count(b"\n") + 1,
                "Wrap the assigned value after the operator.",
            )
            for edit in self._edits(content, rule_config)
        ]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return apply_java_edits(content, self._edits(content, rule_config))


class TernaryLayoutRule(BaseRule):
    rule_id = "IR-ternary-layout"
    description = "Keep fitting ternary expressions compact; otherwise align question and colon branches."
    category = "expressions"
    is_fixable = "yes"
    commit_profile = True
    default_config = {"max_length": 120, "indent_size": 4, "compact_if_fits": True}
    config_options = {
        "max_length": {"default": 120, "description": "Maximum compact expression line length."},
        "indent_size": {"default": 4, "description": "Ternary continuation indentation."},
        "compact_if_fits": {"default": True, "description": "Collapse fitting ternary expressions."},
    }
    cases = [
        RuleCase(
            "compact ternary",
            "class Sample { int value(boolean ready) { return ready\n        ? first()\n        : second(); } int first() { return 1; } int second() { return 2; } }\n",
            "fixed",
            "class Sample { int value(boolean ready) { return ready ? first() : second(); } int first() { return 1; } int second() { return 2; } }\n",
        ),
        RuleCase(
            "compact branch",
            "class Sample { int value(boolean ready) { return ready ? 1 : 2; } }\n",
            "accepted",
        ),
        RuleCase(
            "nested ternary branches",
            "class Sample {\n"
            "    Result choose(State state) {\n"
            "        return (state == State.FIRST) ? Result.FIRST : (state == State.SECOND) ? Result.SECOND : Result.EXTRAORDINARILY_LONG_FALLBACK_RESULT;\n"
            "    }\n"
            "}\n",
            "fixed",
            "class Sample {\n"
            "    Result choose(State state) {\n"
            "        return (state == State.FIRST)\n"
            "            ? Result.FIRST\n"
            "            : (state == State.SECOND)\n"
            "                ? Result.SECOND\n"
            "                : Result.EXTRAORDINARILY_LONG_FALLBACK_RESULT;\n"
            "    }\n"
            "}\n",
        ),
    ]

    @staticmethod
    def _compact_node(document, node) -> Optional[str]:
        text = document.text(node).strip()
        if "\n" not in text:
            return text
        protected = {"line_comment", "block_comment", "string_literal", "character_literal", "text_block"}
        if any(child.type in protected for child in walk(node)):
            return None
        compact = " ".join(text.split())
        for opening, closing in (("(", ")"), ("[", "]"), ("{", "}")):
            compact = compact.replace(opening + " ", opening).replace(" " + closing, closing)
        return compact

    def _compact_ternary(self, document, node) -> Optional[str]:
        condition = node.child_by_field_name("condition")
        consequence = node.child_by_field_name("consequence")
        alternative = node.child_by_field_name("alternative")
        if not condition or not consequence or not alternative:
            return None
        condition_text = self._compact_node(document, condition)
        consequence_text = self._compact_node(document, consequence)
        alternative_text = (
            self._compact_ternary(document, alternative)
            if alternative.type == "ternary_expression"
            else self._compact_node(document, alternative)
        )
        if None in {condition_text, consequence_text, alternative_text}:
            return None
        return f"{condition_text} ? {consequence_text} : {alternative_text}"

    def _multiline_ternary(self, document, node, operator_column: int, size: int) -> Optional[list[str]]:
        condition = node.child_by_field_name("condition")
        consequence = node.child_by_field_name("consequence")
        alternative = node.child_by_field_name("alternative")
        if not condition or not consequence or not alternative:
            return None
        condition_text = self._compact_node(document, condition)
        consequence_text = self._compact_node(document, consequence)
        if condition_text is None or consequence_text is None:
            return None
        indent = " " * operator_column
        lines = [condition_text, f"{indent}? {consequence_text}"]
        if alternative.type == "ternary_expression":
            nested = self._multiline_ternary(document, alternative, operator_column + size, size)
            if nested is None:
                return None
            lines.append(f"{indent}: {nested[0]}")
            lines.extend(nested[1:])
        else:
            alternative_text = self._compact_node(document, alternative)
            if alternative_text is None:
                return None
            lines.append(f"{indent}: {alternative_text}")
        return lines

    def _edits(self, content: str, config: Dict[str, Any]) -> List[JavaEdit]:
        document = parse_java(content)
        maximum = int(config.get("max_length", 120))
        size = int(config.get("indent_size", 4))
        edits = []
        for node in nodes_of_type(document, "ternary_expression"):
            if any(ancestor.type == "ternary_expression" for ancestor in _ancestors(node.parent)):
                continue
            if any(child.type in {"line_comment", "block_comment", "text_block"} for child in walk(node)):
                continue
            compact = self._compact_ternary(document, node)
            if compact is None:
                continue
            prefix = document.content.splitlines()[node.start_point.row][:node.start_point.column]
            suffix_length = len(_terminal_suffix(document, node))
            if (
                config.get("compact_if_fits", True)
                and len(prefix) + len(compact) + suffix_length <= maximum
            ):
                replacement = compact
            else:
                operator_column = _wrapped_continuation_depth(node, "expression") * size
                rendered = self._multiline_ternary(document, node, operator_column, size)
                if rendered is None or any(
                    len(prefix) + len(line) > maximum
                    if index == 0
                    else len(line) + (suffix_length if index == len(rendered) - 1 else 0) > maximum
                    for index, line in enumerate(rendered)
                ):
                    continue
                replacement = "\n".join(rendered)
            if replacement != document.text(node) and edit_is_authorized(node, config):
                edits.append(JavaEdit(node.start_byte, node.end_byte, replacement))
        return edits

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        return [
            _line_violation(self, content, document.source[:edit.start].count(b"\n") + 1, "Use canonical ternary layout.")
            for edit in self._edits(content, rule_config)
        ]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return apply_java_edits(content, self._edits(content, rule_config))


class ArrayInitializerLayoutRule(BaseRule):
    rule_id = "IR-array-initializer-layout"
    description = "Keep fitting array initializers compact; otherwise place each value on its own line."
    category = "variables"
    is_fixable = "yes"
    commit_profile = True
    default_config = {"max_length": 120, "indent_size": 4, "compact_if_fits": True}
    config_options = {
        "max_length": {"default": 120, "description": "Maximum compact initializer line length."},
        "indent_size": {"default": 4, "description": "Initializer continuation indentation."},
        "compact_if_fits": {"default": True, "description": "Collapse fitting initializers."},
    }
    cases = [
        RuleCase(
            "compact initializer",
            "class Sample { int[] values = {\n    1,\n    2\n}; }\n",
            "fixed",
            "class Sample { int[] values = {1, 2}; }\n",
        ),
        RuleCase("compact values", "class Sample { int[] values = {1, 2}; }\n", "accepted"),
        RuleCase(
            "annotation value array",
            "@Labels({\"FirstExtraordinarilyDescriptiveLabel\", \"SecondExtraordinarilyDescriptiveLabel\", \"ThirdExtraordinarilyDescriptiveLabel\"})\n"
            "class Sample {}\n",
            "fixed",
            "@Labels({\n"
            "        \"FirstExtraordinarilyDescriptiveLabel\",\n"
            "        \"SecondExtraordinarilyDescriptiveLabel\",\n"
            "        \"ThirdExtraordinarilyDescriptiveLabel\"\n"
            "    })\n"
            "class Sample {}\n",
        ),
    ]

    def _edits(self, content: str, config: Dict[str, Any]) -> List[JavaEdit]:
        document = parse_java(content)
        maximum = int(config.get("max_length", 120))
        size = int(config.get("indent_size", 4))
        edits = []
        claimed = []
        candidates = list(nodes_of_type(document, "array_initializer", "element_value_array_initializer"))
        for node in sorted(candidates, key=lambda item: item.end_byte - item.start_byte):
            if any(not (node.end_byte <= start or node.start_byte >= end) for start, end in claimed):
                continue
            if any(child.type in {"line_comment", "block_comment"} for child in walk(node)):
                continue
            values = [document.text(child).strip() for child in node.named_children]
            if not values or any("\n" in value for value in values):
                continue
            compact = "{" + ", ".join(values) + "}"
            prefix = document.content.splitlines()[node.start_point.row][:node.start_point.column]
            if config.get("compact_if_fits", True) and len(prefix) + len(compact) <= maximum:
                replacement = compact
            elif len(prefix) + len(compact) > maximum:
                depth = _wrapped_continuation_depth(node, "list")
                indent = " " * (depth * size)
                close_indent = " " * (max(0, depth - 1) * size)
                replacement = "{\n" + ",\n".join(indent + value for value in values) + "\n" + close_indent + "}"
            else:
                continue
            if replacement != document.text(node) and edit_is_authorized(node, config):
                edits.append(JavaEdit(node.start_byte, node.end_byte, replacement))
                claimed.append((node.start_byte, node.end_byte))
        return edits

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        return [
            _line_violation(self, content, document.source[:edit.start].count(b"\n") + 1, "Use canonical array initializer layout.")
            for edit in self._edits(content, rule_config)
        ]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return apply_java_edits(content, self._edits(content, rule_config))


class TryResourceLayoutRule(BaseRule):
    rule_id = "IR-try-resource-layout"
    description = "Keep fitting try resources compact; otherwise place each resource on its own line."
    category = "control-flow"
    is_fixable = "yes"
    commit_profile = True
    default_config = {"max_length": 120, "indent_size": 4, "compact_if_fits": True}
    config_options = {
        "max_length": {"default": 120, "description": "Maximum compact resource line length."},
        "indent_size": {"default": 4, "description": "Resource continuation indentation."},
        "compact_if_fits": {"default": True, "description": "Collapse fitting resource lists."},
    }
    cases = [
        RuleCase(
            "compact resources",
            "class Sample { void run() throws Exception { try (\n    var first = open();\n    var second = open()\n) {} } Object open() { return null; } }\n",
            "fixed",
            "class Sample { void run() throws Exception { try (var first = open(); var second = open()) {} } Object open() { return null; } }\n",
        ),
        RuleCase(
            "single resource",
            "class Sample { void run() throws Exception { try (var value = open()) {} } Object open() { return null; } }\n",
            "accepted",
        ),
    ]

    def _edits(self, content: str, config: Dict[str, Any]) -> List[JavaEdit]:
        document = parse_java(content)
        maximum = int(config.get("max_length", 120))
        size = int(config.get("indent_size", 4))
        edits = []
        for node in nodes_of_type(document, "resource_specification"):
            if any(child.type in {"line_comment", "block_comment"} for child in walk(node)):
                continue
            values = [document.text(child).strip() for child in node.named_children]
            if not values or any("\n" in value for value in values):
                continue
            compact = "(" + "; ".join(values) + ")"
            prefix = document.content.splitlines()[node.start_point.row][:node.start_point.column]
            if config.get("compact_if_fits", True) and len(prefix) + len(compact) <= maximum:
                replacement = compact
            elif len(prefix) + len(compact) > maximum:
                depth = _wrapped_continuation_depth(node, "list")
                indent = " " * (depth * size)
                close_indent = " " * (max(0, depth - 1) * size)
                replacement = "(\n" + ";\n".join(indent + value for value in values) + "\n" + close_indent + ")"
            else:
                continue
            if replacement != document.text(node) and edit_is_authorized(node, config):
                edits.append(JavaEdit(node.start_byte, node.end_byte, replacement))
        return edits

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        return [
            _line_violation(self, content, document.source[:edit.start].count(b"\n") + 1, "Use canonical try-resource layout.")
            for edit in self._edits(content, rule_config)
        ]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return apply_java_edits(content, self._edits(content, rule_config))


class TypeClauseLayoutRule(BaseRule):
    rule_id = "IR-type-clause-layout"
    description = "Keep fitting implements, permits, and throws clauses compact; otherwise list one type per line."
    category = "source-structure"
    is_fixable = "yes"
    commit_profile = True
    default_config = {"max_length": 120, "indent_size": 4, "compact_if_fits": True}
    config_options = {
        "max_length": {"default": 120, "description": "Maximum compact clause line length."},
        "indent_size": {"default": 4, "description": "Type-clause continuation indentation."},
        "compact_if_fits": {"default": True, "description": "Collapse fitting type clauses."},
    }
    cases = [
        RuleCase(
            "compact throws",
            "class Sample { void run() throws\n    FirstProblem,\n    SecondProblem {} }\n",
            "fixed",
            "class Sample { void run() throws FirstProblem, SecondProblem {} }\n",
        ),
        RuleCase("compact implements", "class Sample implements First, Second {}\n", "accepted"),
    ]
    KEYWORDS = {"super_interfaces": "implements", "permits": "permits", "throws": "throws"}

    @staticmethod
    def _values(document, node) -> list[str]:
        children = list(node.named_children)
        if len(children) == 1 and children[0].type == "type_list":
            children = list(children[0].named_children)
        return [document.text(child).strip() for child in children]

    def _edits(self, content: str, config: Dict[str, Any]) -> List[JavaEdit]:
        document = parse_java(content)
        maximum = int(config.get("max_length", 120))
        size = int(config.get("indent_size", 4))
        edits = []
        for node in document.nodes:
            keyword = self.KEYWORDS.get(node.type)
            if not keyword or not node.named_child_count:
                continue
            if any(child.type in {"line_comment", "block_comment"} for child in walk(node)):
                continue
            values = self._values(document, node)
            if not values or any("\n" in value for value in values):
                continue
            compact = keyword + " " + ", ".join(values)
            prefix = document.content.splitlines()[node.start_point.row][:node.start_point.column]
            if config.get("compact_if_fits", True) and len(prefix) + len(compact) <= maximum:
                replacement = compact
            elif len(prefix) + len(compact) > maximum and len(values) > 1:
                indent = " " * (_wrapped_continuation_depth(node, "type") * size)
                replacement = keyword + "\n" + ",\n".join(indent + value for value in values)
            else:
                continue
            if replacement != document.text(node) and edit_is_authorized(node, config):
                edits.append(JavaEdit(node.start_byte, node.end_byte, replacement))
        return edits

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        return [
            _line_violation(self, content, document.source[:edit.start].count(b"\n") + 1, "Use canonical type-clause layout.")
            for edit in self._edits(content, rule_config)
        ]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return apply_java_edits(content, self._edits(content, rule_config))


class AnnotationLayoutRule(BaseRule):
    rule_id = "IR-annotation-layout"
    description = "Place declaration annotations on separate lines before modifiers and declarations."
    category = "source-structure"
    is_fixable = "yes"
    commit_profile = True
    cases = [
        RuleCase(
            "declaration annotations",
            "@Deprecated @SuppressWarnings(\"unused\") public class Sample {}\n",
            "fixed",
            "@Deprecated\n@SuppressWarnings(\"unused\")\npublic class Sample {}\n",
        ),
        RuleCase("separate annotation", "@Deprecated\nclass Sample {}\n", "accepted"),
    ]
    DECLARATIONS = {
        "class_declaration", "interface_declaration", "enum_declaration", "record_declaration",
        "annotation_type_declaration", "method_declaration", "constructor_declaration", "field_declaration",
    }

    def _edits(self, content: str, config: Dict[str, Any]) -> List[JavaEdit]:
        document = parse_java(content)
        edits = []
        for modifiers in nodes_of_type(document, "modifiers"):
            if not modifiers.parent or modifiers.parent.type not in self.DECLARATIONS:
                continue
            children = list(modifiers.children)
            for index, child in enumerate(children):
                if child.type not in {"annotation", "marker_annotation"} or index + 1 >= len(children):
                    continue
                following = children[index + 1]
                gap = document.source[child.end_byte:following.start_byte].decode()
                if "\n" in gap or gap.strip():
                    continue
                line = document.content.splitlines()[child.start_point.row]
                indent = line[: len(line) - len(line.lstrip(" "))]
                if span_is_authorized(document, child.end_byte, following.start_byte, config):
                    edits.append(JavaEdit(child.end_byte, following.start_byte, "\n" + indent))
        return edits

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        return [
            _line_violation(self, content, document.source[:edit.start].count(b"\n") + 1, "Place declaration annotations on separate lines.")
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
        for parent in document.nodes:
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
