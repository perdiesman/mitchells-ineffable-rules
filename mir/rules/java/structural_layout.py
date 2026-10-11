"""Additional syntax-aware Java structure layout rules."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from mir.engine.rule_interface import BaseRule, RuleCase, Violation
from mir.rules.java.java_utils import (
    JavaEdit,
    apply_java_edits,
    edit_is_authorized,
    nodes_of_type,
    parse_java,
    span_is_authorized,
    walk,
)


COMMENT_TYPES = {"line_comment", "block_comment"}
TYPE_BODY_TYPES = {
    "class_body",
    "interface_body",
    "enum_body",
    "annotation_type_body",
}
BEHAVIOR_MEMBER_TYPES = {
    "constructor_declaration",
    "method_declaration",
    "static_initializer",
    "constructor_body",
    "class_declaration",
    "interface_declaration",
    "enum_declaration",
    "record_declaration",
    "annotation_type_declaration",
}


def _violation(rule: BaseRule, content: str, edit: JavaEdit, message: str) -> Violation:
    line = content.count("\n", 0, edit.start) + 1
    lines = content.splitlines()
    return Violation(rule.rule_id, line, message, [lines[line - 1]] if line <= len(lines) else [], True)


def _has_comment(node) -> bool:
    return any(child.type in COMMENT_TYPES for child in walk(node))


def _indent_for(node, size: int, extra: int = 0) -> str:
    return " " * (node.start_point.column + extra * size)


def _first_child(node, node_type: str):
    return next((child for child in node.children if child.type == node_type), None)


def _line_indent(document, row: int) -> int:
    line = document.content.splitlines()[row]
    return len(line) - len(line.lstrip(" "))


class TypeParameterLayoutRule(BaseRule):
    rule_id = "IR-type-parameter-layout"
    description = "Keep fitting generic type parameters compact; otherwise place each parameter on its own line."
    category = "classes/interfaces"
    is_fixable = "yes"
    commit_profile = True
    default_config = {"max_length": 120, "indent_size": 4, "compact_if_fits": True}
    config_options = {
        "max_length": {"default": 120, "description": "Maximum compact declaration length."},
        "indent_size": {"default": 4, "description": "Continuation indentation."},
        "compact_if_fits": {"default": True, "description": "Collapse fitting parameter lists."},
    }
    cases = [
        RuleCase(
            "expanded generic parameters",
            "class Sample<\n    First,\n    Second\n> {}\n",
            "fixed",
            "class Sample<First, Second> {}\n",
        ),
        RuleCase(
            "long generic parameters",
            "class Sample<FirstParameterWithLongName, SecondParameterWithLongName> {}\n",
            "accepted",
        ),
    ]

    def _replacement(self, document, node, config: Dict[str, Any]) -> Optional[str]:
        if _has_comment(node):
            return None
        values = [document.text(child).strip() for child in node.named_children]
        if not values or any("\n" in value for value in values):
            return None
        compact = "<" + ", ".join(values) + ">"
        prefix = document.content.splitlines()[node.start_point.row][:node.start_point.column]
        maximum = int(config.get("max_length", 120))
        if config.get("compact_if_fits", True) and len(prefix) + len(compact) <= maximum:
            return compact if compact != document.text(node) else None
        if len(prefix) + len(compact) <= maximum:
            return None
        size = int(config.get("indent_size", 4))
        base = _line_indent(document, node.start_point.row)
        indent = " " * (base + size)
        close_indent = " " * base
        replacement = "<\n" + ",\n".join(indent + value for value in values) + "\n" + close_indent + ">"
        return replacement if replacement != document.text(node) else None

    def _edits(self, content: str, config: Dict[str, Any]) -> List[JavaEdit]:
        if "<" not in content:
            return []
        document = parse_java(content)
        edits = []
        for node in nodes_of_type(document, "type_parameters"):
            replacement = self._replacement(document, node, config)
            if replacement is not None and edit_is_authorized(node, config):
                edits.append(JavaEdit(node.start_byte, node.end_byte, replacement))
        return edits

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        return [_violation(self, content, edit, "Use canonical generic parameter layout.") for edit in self._edits(content, rule_config)]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return apply_java_edits(content, self._edits(content, rule_config))


class LoopHeaderLayoutRule(BaseRule):
    rule_id = "IR-loop-header-layout"
    description = "Keep fitting for-loop headers compact; otherwise place each logical header part on its own line."
    category = "control-flow"
    is_fixable = "yes"
    commit_profile = True
    default_config = {"max_length": 120, "indent_size": 4, "compact_if_fits": True}
    config_options = {
        "max_length": {"default": 120, "description": "Maximum compact header length."},
        "indent_size": {"default": 4, "description": "Header continuation indentation."},
        "compact_if_fits": {"default": True, "description": "Collapse fitting loop headers."},
    }
    cases = [
        RuleCase(
            "expanded classic loop",
            "class Sample {\n    void run() {\n        for (\n            int index = 0;\n            index < count;\n            index++\n        ) {}\n    }\n}\n",
            "fixed",
            "class Sample {\n    void run() {\n        for (int index = 0; index < count; index++) {}\n    }\n}\n",
        ),
        RuleCase(
            "expanded enhanced loop",
            "class Sample {\n    void run() {\n        for (\n            String value :\n            values\n        ) {}\n    }\n}\n",
            "fixed",
            "class Sample {\n    void run() {\n        for (String value : values) {}\n    }\n}\n",
        ),
    ]

    @staticmethod
    def _bounds(node):
        opening = _first_child(node, "(")
        closing = _first_child(node, ")")
        return opening, closing

    def _parts(self, document, node) -> Optional[tuple[list[str], list[str]]]:
        if node.type == "for_statement":
            fields = [node.child_by_field_name(name) for name in ("init", "condition", "update")]
            if any(field is None for field in fields):
                return None
            values = [document.text(field).strip().removesuffix(";") for field in fields]
            return values, [";", ";", ""]
        type_node = node.child_by_field_name("type")
        name = node.child_by_field_name("name")
        value = node.child_by_field_name("value")
        if not type_node or not name or not value:
            return None
        declaration = document.text(type_node).strip() + " " + document.text(name).strip() + " :"
        return [declaration, document.text(value).strip()], ["", ""]

    def _edits(self, content: str, config: Dict[str, Any]) -> List[JavaEdit]:
        if "for" not in content:
            return []
        document = parse_java(content)
        maximum = int(config.get("max_length", 120))
        size = int(config.get("indent_size", 4))
        edits = []
        for node in nodes_of_type(document, "for_statement", "enhanced_for_statement"):
            opening, closing = self._bounds(node)
            parts = self._parts(document, node)
            if not opening or not closing or not parts or _has_comment(node):
                continue
            values, suffixes = parts
            if any("\n" in value for value in values):
                continue
            if node.type == "for_statement":
                compact = "(" + "; ".join(values) + ")"
            else:
                compact = "(" + values[0] + " " + values[1] + ")"
            prefix = document.content.splitlines()[opening.start_point.row][:opening.start_point.column]
            original = document.source[opening.start_byte:closing.end_byte].decode()
            if config.get("compact_if_fits", True) and len(prefix) + len(compact) <= maximum:
                replacement = compact
            elif len(prefix) + len(compact) > maximum:
                base = _line_indent(document, node.start_point.row)
                indent = " " * (base + size)
                close_indent = " " * base
                rendered = [indent + value + suffix for value, suffix in zip(values, suffixes)]
                replacement = "(\n" + "\n".join(rendered) + "\n" + close_indent + ")"
            else:
                continue
            if replacement != original and span_is_authorized(document, opening.start_byte, closing.end_byte, config):
                edits.append(JavaEdit(opening.start_byte, closing.end_byte, replacement))
        return edits

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        return [_violation(self, content, edit, "Use canonical for-loop header layout.") for edit in self._edits(content, rule_config)]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return apply_java_edits(content, self._edits(content, rule_config))


class EnumLayoutRule(BaseRule):
    rule_id = "IR-enum-layout"
    description = "Keep fitting enum constants together; otherwise place each constant on its own line."
    category = "classes/interfaces"
    is_fixable = "yes"
    commit_profile = True
    default_config = {"max_length": 120, "indent_size": 4, "compact_if_fits": True}
    config_options = {
        "max_length": {"default": 120, "description": "Maximum compact constant line length."},
        "indent_size": {"default": 4, "description": "Enum-body indentation."},
        "compact_if_fits": {"default": True, "description": "Keep fitting constants on one line."},
    }
    cases = [
        RuleCase(
            "compact constants",
            "enum Status {\n    READY,\n    RUNNING,\n    DONE\n}\n",
            "fixed",
            "enum Status {\n    READY, RUNNING, DONE\n}\n",
        ),
        RuleCase("fitting constants", "enum Status {\n    READY, RUNNING, DONE\n}\n", "accepted"),
    ]

    def _edits(self, content: str, config: Dict[str, Any]) -> List[JavaEdit]:
        if "enum" not in content:
            return []
        document = parse_java(content)
        maximum = int(config.get("max_length", 120))
        size = int(config.get("indent_size", 4))
        comments = list(nodes_of_type(document, *COMMENT_TYPES))
        edits = []
        for body in nodes_of_type(document, "enum_body"):
            constants = [child for child in body.named_children if child.type == "enum_constant"]
            if not constants or any(_has_comment(constant) for constant in constants):
                continue
            values = [document.text(constant).strip() for constant in constants]
            if any("\n" in value for value in values):
                continue
            first, last = constants[0], constants[-1]
            if any(first.start_byte <= comment.start_byte < last.end_byte for comment in comments):
                continue
            compact = ", ".join(values)
            prefix_length = first.start_point.column
            if config.get("compact_if_fits", True) and prefix_length + len(compact) <= maximum:
                replacement = compact
            elif prefix_length + len(compact) > maximum:
                base = _line_indent(document, body.parent.start_point.row)
                indent = " " * (base + size)
                replacement = values[0] + ",\n" + ",\n".join(indent + value for value in values[1:])
            else:
                continue
            original = document.source[first.start_byte:last.end_byte].decode()
            if replacement != original and span_is_authorized(document, first.start_byte, last.end_byte, config):
                edits.append(JavaEdit(first.start_byte, last.end_byte, replacement))
        return edits

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        return [_violation(self, content, edit, "Use canonical enum constant layout.") for edit in self._edits(content, rule_config)]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return apply_java_edits(content, self._edits(content, rule_config))


class EmptyBodyLayoutRule(BaseRule):
    rule_id = "IR-empty-body-layout"
    description = "Write empty Java declaration and executable bodies as compact braces."
    category = "whitespace/layout"
    is_fixable = "yes"
    commit_profile = True
    cases = [
        RuleCase(
            "empty method body",
            "class Sample {\n    void reset() {\n    }\n}\n",
            "fixed",
            "class Sample {\n    void reset() {}\n}\n",
        ),
        RuleCase("commented body", "class Sample {\n    void reset() {\n        // Deliberately empty.\n    }\n}\n", "accepted"),
    ]
    BODY_TYPES = TYPE_BODY_TYPES | {"block", "constructor_body"}

    def _edits(self, content: str, config: Dict[str, Any]) -> List[JavaEdit]:
        if "{\n" not in content and "{\r\n" not in content:
            return []
        document = parse_java(content)
        edits = []
        for node in nodes_of_type(document, *self.BODY_TYPES):
            if node.named_child_count or _has_comment(node):
                continue
            if document.text(node) == "{}":
                continue
            if edit_is_authorized(node, config):
                edits.append(JavaEdit(node.start_byte, node.end_byte, "{}"))
        return edits

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        return [_violation(self, content, edit, "Compact the empty body.") for edit in self._edits(content, rule_config)]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return apply_java_edits(content, self._edits(content, rule_config))


class MemberSpacingRule(BaseRule):
    rule_id = "IR-member-spacing"
    description = "Group adjacent fields and separate constructors, methods, initializers, and nested types with one blank line."
    category = "classes/interfaces"
    is_fixable = "yes"
    commit_profile = True
    cases = [
        RuleCase(
            "separate behavioral members",
            "class Sample {\n    int first;\n    int second;\n    Sample() {}\n    void run() {}\n}\n",
            "fixed",
            "class Sample {\n    int first;\n    int second;\n\n    Sample() {}\n\n    void run() {}\n}\n",
        ),
        RuleCase("group fields", "class Sample {\n    int first;\n    int second;\n}\n", "accepted"),
    ]

    @staticmethod
    def _members(body) -> list:
        return [child for child in body.named_children if child.type not in COMMENT_TYPES]

    def _edits(self, content: str, config: Dict[str, Any]) -> List[JavaEdit]:
        document = parse_java(content)
        comments = list(nodes_of_type(document, *COMMENT_TYPES))
        edits = []
        for body in nodes_of_type(document, *TYPE_BODY_TYPES):
            members = self._members(body)
            for left, right in zip(members, members[1:]):
                if left.type == "enum_constant" or right.type == "enum_constant":
                    continue
                if left.type == "field_declaration" and right.type == "field_declaration":
                    continue
                if left.type not in BEHAVIOR_MEMBER_TYPES and right.type not in BEHAVIOR_MEMBER_TYPES:
                    continue
                gap = document.source[left.end_byte:right.start_byte].decode()
                if gap.strip() or any(
                    left.end_byte <= comment.start_byte < right.start_byte
                    for comment in comments
                ):
                    continue
                indent = " " * right.start_point.column
                replacement = "\n\n" + indent
                if gap != replacement and span_is_authorized(document, left.end_byte, right.start_byte, config):
                    edits.append(JavaEdit(left.end_byte, right.start_byte, replacement))
        return edits

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        return [_violation(self, content, edit, "Separate Java members with one blank line.") for edit in self._edits(content, rule_config)]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return apply_java_edits(content, self._edits(content, rule_config))


class ParameterAnnotationLayoutRule(BaseRule):
    rule_id = "IR-parameter-annotation-layout"
    description = "Keep fitting parameter annotations compact; otherwise place each annotation and the declared type on its own line."
    category = "methods"
    is_fixable = "yes"
    commit_profile = True
    default_config = {"max_length": 120, "indent_size": 4, "compact_if_fits": True}
    config_options = {
        "max_length": {"default": 120, "description": "Maximum compact parameter line length."},
        "indent_size": {"default": 4, "description": "Parameter continuation indentation."},
        "compact_if_fits": {"default": True, "description": "Collapse fitting annotated parameters."},
    }
    cases = [
        RuleCase(
            "long annotated parameter",
            "class Sample {\n"
            "    void publish(\n"
            "        @OptionalValue @RequestValue(name = \"category\", required = false) @Converted(format = \"timestamp-with-zone\") OffsetDateTime startTime\n"
            "    ) {}\n"
            "}\n",
            "fixed",
            "class Sample {\n"
            "    void publish(\n"
            "        @OptionalValue\n"
            "        @RequestValue(name = \"category\", required = false)\n"
            "        @Converted(format = \"timestamp-with-zone\")\n"
            "        OffsetDateTime startTime\n"
            "    ) {}\n"
            "}\n",
        ),
        RuleCase(
            "compact annotation",
            "class Sample { void publish(@Named String value) {} }\n",
            "accepted",
        ),
    ]

    @staticmethod
    def _annotations(modifiers) -> list:
        return [
            child for child in modifiers.children
            if child.type in {"annotation", "marker_annotation"}
        ]

    def _edits(self, content: str, config: Dict[str, Any]) -> List[JavaEdit]:
        if "@" not in content:
            return []
        document = parse_java(content)
        lines = document.content.splitlines()
        maximum = int(config.get("max_length", 120))
        edits = []
        for parameter in nodes_of_type(document, "formal_parameter", "spread_parameter"):
            modifiers = next(
                (child for child in parameter.named_children if child.type == "modifiers"),
                None,
            )
            if modifiers is None or _has_comment(parameter):
                continue
            annotations = self._annotations(modifiers)
            if not annotations:
                continue
            compact = " ".join(document.text(parameter).split())
            prefix = lines[parameter.start_point.row][:parameter.start_point.column]
            suffix = lines[parameter.end_point.row][parameter.end_point.column:].rstrip()
            physical_length = len(lines[parameter.start_point.row])
            fits = (
                len(prefix) + len(compact) + len(suffix) <= maximum
                and physical_length <= maximum
            )
            size = int(config.get("indent_size", 4))
            parameter_indent = (
                parameter.start_point.column
                if not prefix.strip()
                else _line_indent(document, parameter.start_point.row) + size
            )
            indent = " " * parameter_indent
            desired = " " if config.get("compact_if_fits", True) and fits else "\n" + indent
            declared_type = next(
                (child for child in parameter.named_children if child.start_byte >= modifiers.end_byte),
                None,
            )
            following_nodes = annotations[1:] + [declared_type]
            for annotation, following in zip(annotations, following_nodes):
                if following is None or following.start_byte < annotation.end_byte:
                    continue
                gap = document.source[annotation.end_byte:following.start_byte].decode()
                if gap.strip() or gap == desired:
                    continue
                if span_is_authorized(document, annotation.end_byte, following.start_byte, config):
                    edits.append(JavaEdit(annotation.end_byte, following.start_byte, desired))
        return edits

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        return [
            _violation(self, content, edit, "Use canonical parameter annotation layout.")
            for edit in self._edits(content, rule_config)
        ]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return apply_java_edits(content, self._edits(content, rule_config))


class LambdaLayoutRule(BaseRule):
    rule_id = "IR-lambda-layout"
    description = "Keep fitting lambda expressions compact and indent wrapped expression bodies after the arrow."
    category = "expressions"
    is_fixable = "yes"
    commit_profile = True
    default_config = {"max_length": 120, "indent_size": 4, "compact_if_fits": True}
    config_options = {
        "max_length": {"default": 120, "description": "Maximum compact lambda length."},
        "indent_size": {"default": 4, "description": "Expression-body continuation indentation."},
        "compact_if_fits": {"default": True, "description": "Collapse fitting expression lambdas."},
    }
    cases = [
        RuleCase(
            "compact expression lambda",
            "class Sample {\n    Object map(Object value) {\n        return apply(value ->\n            transform(value));\n    }\n    Object apply(Object value) { return value; }\n    Object transform(Object value) { return value; }\n}\n",
            "fixed",
            "class Sample {\n    Object map(Object value) {\n        return apply(value -> transform(value));\n    }\n    Object apply(Object value) { return value; }\n    Object transform(Object value) { return value; }\n}\n",
        ),
        RuleCase("block lambda", "class Sample { Object value = (Runnable) () -> {}; }\n", "accepted"),
    ]

    def _edits(self, content: str, config: Dict[str, Any]) -> List[JavaEdit]:
        if "->" not in content:
            return []
        document = parse_java(content)
        comments = list(nodes_of_type(document, *COMMENT_TYPES))
        maximum = int(config.get("max_length", 120))
        size = int(config.get("indent_size", 4))
        edits = []
        for node in nodes_of_type(document, "lambda_expression"):
            parameters = node.child_by_field_name("parameters")
            body = node.child_by_field_name("body")
            arrow = next((child for child in node.children if child.type == "->"), None)
            if not parameters or not body or not arrow:
                continue
            if any(
                parameters.end_byte <= comment.start_byte < body.start_byte
                for comment in comments
            ):
                continue
            parameter_text = document.text(parameters).strip()
            body_text = document.text(body).strip()
            prefix = document.content.splitlines()[node.start_point.row][:node.start_point.column]
            compact_length = len(prefix) + len(parameter_text) + 4 + len(body_text)
            before = document.source[parameters.end_byte:arrow.start_byte].decode()
            after = document.source[arrow.end_byte:body.start_byte].decode()
            if body.type == "block":
                desired_before = " "
                desired_after = " "
            elif (
                config.get("compact_if_fits", True)
                and "\n" not in parameter_text
                and "\n" not in body_text
                and compact_length <= maximum
            ):
                desired_before = " "
                desired_after = " "
            elif "\n" in after:
                # Once a complex body is wrapped, JavaIndentRule owns its exact
                # nesting depth. Keeping the existing newline prevents this
                # rule from fighting expression/list indentation.
                desired_before = " "
                desired_after = after
            else:
                desired_before = " "
                base = _line_indent(document, node.start_point.row)
                desired_after = "\n" + " " * (base + size)
            if before != desired_before and span_is_authorized(document, parameters.end_byte, arrow.start_byte, config):
                edits.append(JavaEdit(parameters.end_byte, arrow.start_byte, desired_before))
            if after != desired_after and span_is_authorized(document, arrow.end_byte, body.start_byte, config):
                edits.append(JavaEdit(arrow.end_byte, body.start_byte, desired_after))
        return edits

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        return [_violation(self, content, edit, "Use canonical lambda layout.") for edit in self._edits(content, rule_config)]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return apply_java_edits(content, self._edits(content, rule_config))


class SwitchLayoutRule(BaseRule):
    rule_id = "IR-switch-layout"
    description = "Place switch cases and colon-style case statements on readable, consistently indented lines."
    category = "control-flow"
    is_fixable = "yes"
    commit_profile = True
    default_config = {"max_length": 120, "indent_size": 4}
    config_options = {
        "max_length": {"default": 120, "description": "Maximum compact arrow-case length."},
        "indent_size": {"default": 4, "description": "Case-body indentation."},
    }
    cases = [
        RuleCase(
            "colon switch groups",
            "class Sample {\n    int value(int code) {\n        switch (code) { case 1: prepare(); return 1; default: return 0; }\n    }\n    void prepare() {}\n}\n",
            "fixed",
            "class Sample {\n    int value(int code) {\n        switch (code) {\n            case 1:\n                prepare();\n                return 1;\n            default:\n                return 0;\n        }\n    }\n    void prepare() {}\n}\n",
        ),
        RuleCase(
            "arrow switch rules",
            "class Sample {\n    int value(int code) {\n        return switch (code) { case 1 -> 1; default -> 0; };\n    }\n}\n",
            "fixed",
            "class Sample {\n    int value(int code) {\n        return switch (code) {\n            case 1 -> 1;\n            default -> 0;\n        };\n    }\n}\n",
        ),
    ]

    @staticmethod
    def _comments_between(comments: Iterable, start: int, end: int) -> bool:
        return any(start <= comment.start_byte < end for comment in comments)

    def _gap_edit(self, document, comments, start: int, end: int, replacement: str, config: Dict[str, Any]) -> Optional[JavaEdit]:
        if self._comments_between(comments, start, end):
            return None
        original = document.source[start:end].decode()
        if original == replacement or original.strip():
            return None
        if not span_is_authorized(document, start, end, config):
            return None
        return JavaEdit(start, end, replacement)

    def _edits(self, content: str, config: Dict[str, Any]) -> List[JavaEdit]:
        if "switch" not in content:
            return []
        document = parse_java(content)
        comments = list(nodes_of_type(document, *COMMENT_TYPES))
        switch_blocks = list(nodes_of_type(document, "switch_block"))
        switch_groups = list(nodes_of_type(document, "switch_block_statement_group"))
        switch_rules = list(nodes_of_type(document, "switch_rule"))
        size = int(config.get("indent_size", 4))
        maximum = int(config.get("max_length", 120))
        edits = []
        for block in switch_blocks:
            opening = _first_child(block, "{")
            closing = _first_child(block, "}")
            children = [
                child for child in block.named_children
                if child.type in {"switch_rule", "switch_block_statement_group"}
            ]
            if not opening or not closing or not children:
                continue
            base = _line_indent(document, block.parent.start_point.row)
            case_indent = " " * (base + size)
            pairs = [(opening.end_byte, children[0].start_byte)]
            pairs.extend((left.end_byte, right.start_byte) for left, right in zip(children, children[1:]))
            for start, end in pairs:
                edit = self._gap_edit(document, comments, start, end, "\n" + case_indent, config)
                if edit:
                    edits.append(edit)
            close_indent = " " * base
            edit = self._gap_edit(document, comments, children[-1].end_byte, closing.start_byte, "\n" + close_indent, config)
            if edit:
                edits.append(edit)

        for group in switch_groups:
            label = next((child for child in group.named_children if child.type == "switch_label"), None)
            colon = _first_child(group, ":")
            statements = [child for child in group.named_children if child is not label]
            if not label or not colon or not statements:
                continue
            switch_block = group.parent
            base = _line_indent(document, switch_block.parent.start_point.row)
            indent = " " * (base + 2 * size)
            pairs = [(colon.end_byte, statements[0].start_byte)]
            pairs.extend((left.end_byte, right.start_byte) for left, right in zip(statements, statements[1:]))
            for start, end in pairs:
                edit = self._gap_edit(document, comments, start, end, "\n" + indent, config)
                if edit:
                    edits.append(edit)

        for rule in switch_rules:
            label = next((child for child in rule.named_children if child.type == "switch_label"), None)
            arrow = _first_child(rule, "->")
            body = rule.named_children[-1] if rule.named_children else None
            if not label or not arrow or not body:
                continue
            before = self._gap_edit(document, comments, label.end_byte, arrow.start_byte, " ", config)
            if before:
                edits.append(before)
            prefix = document.content.splitlines()[label.start_point.row][:label.start_point.column]
            compact_length = len(prefix) + len(document.text(rule).replace("\n", " "))
            switch_block = rule.parent
            base = _line_indent(document, switch_block.parent.start_point.row)
            after_text = " " if body.type == "block" or compact_length <= maximum else "\n" + " " * (base + 2 * size)
            after = self._gap_edit(document, comments, arrow.end_byte, body.start_byte, after_text, config)
            if after:
                edits.append(after)
        return edits

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        return [_violation(self, content, edit, "Use canonical switch layout.") for edit in self._edits(content, rule_config)]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return apply_java_edits(content, self._edits(content, rule_config))
