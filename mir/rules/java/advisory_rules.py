"""Conservative Java best-practice and naming checks."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional

from mir.engine.rule_interface import BaseRule, RuleCase, Violation
from mir.rules.java.java_utils import JavaEdit, apply_java_edits, nodes_of_type, parse_java, walk


WARNING_CONFIG = {"severity": "warning"}
WARNING_OPTION = {"severity": {"default": "warning", "description": "Violation severity."}}
SEMANTIC_CONFIG = {"severity": "warning", "semantic_fix": False}
SEMANTIC_OPTIONS = {
    "severity": {"default": "warning", "description": "Violation severity."},
    "semantic_fix": {"default": False, "description": "Allow the optional source rewrite in normal --fix mode."},
}


def _violation(rule: BaseRule, content: str, node, message: str, fixable: bool = False) -> Violation:
    line = node.start_point.row + 1
    lines = content.splitlines()
    return Violation(rule.rule_id, line, message, [lines[line - 1]] if line <= len(lines) else [], fixable)


def _semantic_enabled(config: Dict[str, Any]) -> bool:
    return bool(config.get("semantic_fix", False)) and config.get("_profile") != "commit"


class RedundantImportsRule(BaseRule):
    rule_id = "IR-redundant-imports"
    description = "Remove duplicate, java.lang, and same-package imports."
    category = "imports"
    is_fixable = "sometimes"
    default_config = SEMANTIC_CONFIG
    config_options = SEMANTIC_OPTIONS
    cases = [
        RuleCase("java lang import", "package sample;\nimport java.lang.String;\nclass Sample {}\n", "not_fixed"),
        RuleCase("needed import", "package sample;\nimport java.util.List;\nclass Sample {}\n", "accepted"),
    ]

    def _redundant(self, content: str):
        document = parse_java(content)
        package = next(nodes_of_type(document, "package_declaration"), None)
        package_name = ""
        if package:
            package_name = document.text(package).removeprefix("package").removesuffix(";").strip()
        seen = set()
        result = []
        for node in nodes_of_type(document, "import_declaration"):
            text = document.text(node).strip()
            name = text.removeprefix("import ").removeprefix("static ").removesuffix(";")
            container = name.rsplit(".", 1)[0] if "." in name else ""
            redundant = text in seen or name.startswith("java.lang.") or (package_name and container == package_name)
            seen.add(text)
            if redundant:
                result.append(node)
        return document, result

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        _, nodes = self._redundant(content)
        fixable = _semantic_enabled(rule_config)
        return [_violation(self, content, node, "Remove the redundant import.", fixable) for node in nodes]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        if not _semantic_enabled(rule_config):
            return content
        document, nodes = self._redundant(content)
        edits = []
        for node in nodes:
            end = node.end_byte
            if document.source[end:end + 2] == b"\r\n":
                end += 2
            elif document.source[end:end + 1] == b"\n":
                end += 1
            edits.append(JavaEdit(node.start_byte, end, ""))
        return apply_java_edits(content, edits)


class OneTopLevelTypeRule(BaseRule):
    rule_id = "IR-one-top-level-type"
    description = "Keep one top-level Java type per ordinary source file and match its filename."
    category = "source-structure"
    is_fixable = "no"
    default_config = WARNING_CONFIG
    config_options = WARNING_OPTION
    cases = [
        RuleCase("multiple types", "class First {}\nclass Second {}\n", "reported"),
        RuleCase("single type", "class Sample {}\n", "accepted"),
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        types = [
            child for child in document.root.named_children
            if child.type in {"class_declaration", "interface_declaration", "enum_declaration", "record_declaration", "annotation_type_declaration"}
        ]
        return [
            _violation(self, content, node, "Move the additional top-level type to its own file.")
            for node in types[1:]
        ]


class OneVariableDeclarationRule(BaseRule):
    rule_id = "IR-one-variable-declaration"
    description = "Declare one field or local variable per declaration outside for-loop headers."
    category = "variables"
    is_fixable = "no"
    default_config = WARNING_CONFIG
    config_options = WARNING_OPTION
    cases = [
        RuleCase("multiple fields", "class Sample { int first, second; }\n", "reported"),
        RuleCase("separate fields", "class Sample { int first; int second; }\n", "accepted"),
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        violations = []
        for node in walk(document.root):
            if node.type not in {"field_declaration", "local_variable_declaration"}:
                continue
            if sum(child.type == "variable_declarator" for child in node.named_children) > 1:
                violations.append(_violation(self, content, node, "Split variables into separate declarations."))
        return violations


class ArrayTypeStyleRule(BaseRule):
    rule_id = "IR-array-type-style"
    description = "Attach array brackets to the type rather than the variable name."
    category = "variables"
    is_fixable = "no"
    default_config = WARNING_CONFIG
    config_options = WARNING_OPTION
    cases = [
        RuleCase("C-style array", "class Sample { String values[]; }\n", "reported"),
        RuleCase("type-style array", "class Sample { String[] values; }\n", "accepted"),
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        violations = []
        for node in nodes_of_type(document, "variable_declarator"):
            name = node.child_by_field_name("name")
            if name and any(child.type == "dimensions" and child.start_byte >= name.end_byte for child in node.children):
                violations.append(_violation(self, content, node, "Write array brackets with the declared type."))
        return violations


class LongLiteralSuffixRule(BaseRule):
    rule_id = "IR-long-literal-suffix"
    description = "Use an uppercase L suffix for long integer literals."
    category = "general"
    is_fixable = "sometimes"
    default_config = SEMANTIC_CONFIG
    config_options = SEMANTIC_OPTIONS
    cases = [
        RuleCase("lowercase suffix", "class Sample { long value = 25l; }\n", "not_fixed"),
        RuleCase("uppercase suffix", "class Sample { long value = 25L; }\n", "accepted"),
    ]

    def _nodes(self, content: str):
        document = parse_java(content)
        return document, [
            node for node in walk(document.root)
            if node.type in {"decimal_integer_literal", "hex_integer_literal", "octal_integer_literal", "binary_integer_literal"}
            and document.text(node).endswith("l")
        ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        _, nodes = self._nodes(content)
        return [_violation(self, content, node, "Use uppercase L for a long literal.", _semantic_enabled(rule_config)) for node in nodes]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        if not _semantic_enabled(rule_config):
            return content
        document, nodes = self._nodes(content)
        return apply_java_edits(content, [
            JavaEdit(node.end_byte - 1, node.end_byte, "L") for node in nodes
        ])


class RedundantBooleanComparisonRule(BaseRule):
    rule_id = "IR-redundant-boolean-comparison"
    description = "Avoid explicit comparisons with true or false when the boolean expression is clear."
    category = "expressions"
    is_fixable = "sometimes"
    default_config = SEMANTIC_CONFIG
    config_options = SEMANTIC_OPTIONS
    cases = [
        RuleCase("true comparison", "class Sample { boolean run(boolean ready) { return ready == true; } }\n", "not_fixed"),
        RuleCase("direct boolean", "class Sample { boolean run(boolean ready) { return ready; } }\n", "accepted"),
    ]

    def _items(self, content: str):
        document = parse_java(content)
        items = []
        for node in nodes_of_type(document, "binary_expression"):
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            operator = next((document.text(child) for child in node.children if not child.is_named), "")
            if not left or not right or operator not in {"==", "!="}:
                continue
            left_text, right_text = document.text(left), document.text(right)
            if right_text in {"true", "false"}:
                expression, literal = left_text, right_text
            elif left_text in {"true", "false"}:
                expression, literal = right_text, left_text
            else:
                continue
            positive = (operator == "==") == (literal == "true")
            replacement = expression if positive else "!(" + expression + ")"
            items.append((node, replacement))
        return document, items

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        _, items = self._items(content)
        return [_violation(self, content, node, "Remove the redundant boolean comparison.", _semantic_enabled(rule_config)) for node, _ in items]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        if not _semantic_enabled(rule_config):
            return content
        _, items = self._items(content)
        return apply_java_edits(content, [JavaEdit(node.start_byte, node.end_byte, replacement) for node, replacement in items])


class EmptyStatementRule(BaseRule):
    rule_id = "IR-empty-statement"
    description = "Do not use an accidental empty statement as a control-flow body."
    category = "correctness"
    is_fixable = "no"
    cases = [
        RuleCase("empty if", "class Sample { void run(boolean ready) { if (ready); } }\n", "reported"),
        RuleCase("empty block", "class Sample { void run(boolean ready) { if (ready) {} } }\n", "accepted"),
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        return [
            _violation(self, content, node, "Replace the empty statement with an explicit block or body.")
            for node in walk(document.root)
            if node.type == ";" and node.parent and node.parent.type in {
                "if_statement", "for_statement", "enhanced_for_statement", "while_statement", "do_statement"
            }
        ]


class AssignmentInConditionRule(BaseRule):
    rule_id = "IR-assignment-in-condition"
    description = "Avoid assignments inside control-flow conditions."
    category = "correctness"
    is_fixable = "no"
    default_config = WARNING_CONFIG
    config_options = WARNING_OPTION
    cases = [
        RuleCase("assignment condition", "class Sample { void run(boolean ready) { if (ready = next()) {} } boolean next() { return true; } }\n", "reported"),
        RuleCase("comparison condition", "class Sample { void run(int value) { if (value == next()) {} } int next() { return 1; } }\n", "accepted"),
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        violations = []
        for node in nodes_of_type(document, "assignment_expression"):
            current = node.parent
            while current and current.type in {"parenthesized_expression", "binary_expression", "unary_expression", "update_expression"}:
                current = current.parent
            if current and current.type in {"if_statement", "while_statement", "do_statement", "for_statement"}:
                violations.append(_violation(self, content, node, "Move the assignment outside the condition."))
        return violations


class EmptyCatchRule(BaseRule):
    rule_id = "IR-empty-catch"
    description = "Explain or handle intentionally ignored exceptions."
    category = "correctness"
    is_fixable = "no"
    default_config = WARNING_CONFIG
    config_options = WARNING_OPTION
    cases = [
        RuleCase("empty catch", "class Sample { void run() { try { execute(); } catch (Exception exception) {} } void execute() {} }\n", "reported"),
        RuleCase("explained catch", "class Sample { void run() { try { execute(); } catch (Exception exception) { /* intentionally ignored */ } } void execute() {} }\n", "accepted"),
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        violations = []
        for catch in nodes_of_type(document, "catch_clause"):
            body = next((child for child in catch.named_children if child.type == "block"), None)
            if body and not body.named_children:
                violations.append(_violation(self, content, catch, "Handle the exception or explain why it is ignored."))
        return violations


class RequiredBracesRule(BaseRule):
    rule_id = "IR-required-braces"
    description = "Use braces for if, else, for, while, and do bodies."
    category = "control-flow"
    is_fixable = "sometimes"
    default_config = SEMANTIC_CONFIG
    config_options = SEMANTIC_OPTIONS
    cases = [
        RuleCase("unbraced if", "class Sample { void run(boolean ready) { if (ready) execute(); } void execute() {} }\n", "not_fixed"),
        RuleCase("braced if", "class Sample { void run(boolean ready) { if (ready) { execute(); } } void execute() {} }\n", "accepted"),
    ]

    def _bodies(self, content: str):
        document = parse_java(content)
        bodies = []
        for node in walk(document.root):
            fields = []
            if node.type == "if_statement":
                fields = ["consequence", "alternative"]
            elif node.type in {"for_statement", "enhanced_for_statement", "while_statement", "do_statement"}:
                fields = ["body"]
            for field in fields:
                body = node.child_by_field_name(field)
                if body and body.type not in {"block", "if_statement"}:
                    bodies.append(body)
        return document, bodies

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        _, bodies = self._bodies(content)
        can_fix = _semantic_enabled(rule_config)
        return [_violation(self, content, body, "Wrap the control-flow body in braces.", can_fix) for body in bodies]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        if not _semantic_enabled(rule_config):
            return content
        document, bodies = self._bodies(content)
        edits = []
        for body in bodies:
            text = document.text(body)
            if "\n" in text or any(child.type in {"line_comment", "block_comment"} for child in walk(body)):
                continue
            line = content.splitlines()[body.start_point.row]
            owner_indent = len(line) - len(line.lstrip(" "))
            replacement = "{\n" + " " * (owner_indent + 4) + text.strip() + "\n" + " " * owner_indent + "}"
            edits.append(JavaEdit(body.start_byte, body.end_byte, replacement))
        return apply_java_edits(content, edits)


class ModifierOrderRule(BaseRule):
    rule_id = "IR-modifier-order"
    description = "Use the standard Java modifier order."
    category = "source-structure"
    is_fixable = "yes"
    commit_profile = True
    commit_semantic_rewrite = True
    cases = [
        RuleCase("unordered modifiers", "final public static class Sample {}\n", "fixed", "public static final class Sample {}\n"),
        RuleCase("ordered modifiers", "public static final class Sample {}\n", "accepted"),
    ]
    ORDER = [
        "public", "protected", "private", "abstract", "default", "static", "final", "sealed", "non-sealed",
        "transient", "volatile", "synchronized", "native", "strictfp",
    ]

    def _edits(self, content: str):
        document = parse_java(content)
        rank = {value: index for index, value in enumerate(self.ORDER)}
        edits = []
        for node in nodes_of_type(document, "modifiers"):
            values = [document.text(child) for child in node.children]
            if any(value.startswith("@") for value in values):
                continue
            ordered = sorted(values, key=lambda value: rank.get(value, len(rank)))
            replacement = " ".join(ordered)
            if replacement != document.text(node):
                edits.append(JavaEdit(node.start_byte, node.end_byte, replacement))
        return edits

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        return [_violation(self, content, next(node for node in nodes_of_type(document, "modifiers") if node.start_byte == edit.start), "Use standard modifier order.", True) for edit in self._edits(content)]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        return apply_java_edits(content, self._edits(content))


class _NamingRuleMixin:
    pattern = r".*"
    node_types: set[str] = set()
    field = "name"

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        pattern = re.compile(str(rule_config.get("pattern", self.pattern)))
        violations = []
        for node in walk(document.root):
            if node.type not in self.node_types:
                continue
            name = node.child_by_field_name(self.field)
            if name and not pattern.fullmatch(document.text(name)):
                violations.append(_violation(self, content, name, f"Name must match {pattern.pattern}."))
        return violations


class TypeNameRule(_NamingRuleMixin, BaseRule):
    rule_id = "IR-type-name"
    description = "Use UpperCamelCase Java type names."
    category = "naming"
    is_fixable = "no"
    default_config = {"severity": "warning", "pattern": r"[A-Z][A-Za-z0-9]*"}
    config_options = {**WARNING_OPTION, "pattern": {"default": r"[A-Z][A-Za-z0-9]*", "description": "Allowed type-name pattern."}}
    pattern = r"[A-Z][A-Za-z0-9]*"
    node_types = {"class_declaration", "interface_declaration", "enum_declaration", "record_declaration", "annotation_type_declaration"}
    cases = [
        RuleCase("lowercase type", "class sample {}\n", "reported"),
        RuleCase("camel type", "class SampleValue {}\n", "accepted"),
    ]


class MethodNameRule(_NamingRuleMixin, BaseRule):
    rule_id = "IR-method-name"
    description = "Use lowerCamelCase Java method names."
    category = "naming"
    is_fixable = "no"
    default_config = {"severity": "warning", "pattern": r"[a-z][A-Za-z0-9]*"}
    config_options = {**WARNING_OPTION, "pattern": {"default": r"[a-z][A-Za-z0-9]*", "description": "Allowed method-name pattern."}}
    pattern = r"[a-z][A-Za-z0-9]*"
    node_types = {"method_declaration"}
    cases = [
        RuleCase("uppercase method", "class Sample { void Execute() {} }\n", "reported"),
        RuleCase("camel method", "class Sample { void executeValue() {} }\n", "accepted"),
    ]


class VariableNameRule(BaseRule):
    rule_id = "IR-variable-name"
    description = "Use lowerCamelCase for Java fields, parameters, and local variables."
    category = "naming"
    is_fixable = "no"
    default_config = {"severity": "warning", "pattern": r"[a-z][A-Za-z0-9]*"}
    config_options = {**WARNING_OPTION, "pattern": {"default": r"[a-z][A-Za-z0-9]*", "description": "Allowed variable-name pattern."}}
    cases = [
        RuleCase("underscore variable", "class Sample { int item_count; }\n", "reported"),
        RuleCase("camel variable", "class Sample { int itemCount; }\n", "accepted"),
    ]

    @staticmethod
    def _constant_declarator(node) -> bool:
        current = node.parent
        while current and current.type not in {"field_declaration", "local_variable_declaration"}:
            current = current.parent
        if not current or current.type != "field_declaration":
            return False
        modifiers = next((child for child in current.children if child.type == "modifiers"), None)
        if not modifiers:
            return False
        values = {child.type for child in modifiers.children}
        return {"static", "final"}.issubset(values)

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        pattern = re.compile(str(rule_config.get("pattern", r"[a-z][A-Za-z0-9]*")))
        names = []
        for node in walk(document.root):
            if node.type == "variable_declarator" and not self._constant_declarator(node):
                name = node.child_by_field_name("name")
                if name:
                    names.append(name)
            elif node.type in {"formal_parameter", "spread_parameter", "catch_formal_parameter"}:
                name = node.child_by_field_name("name")
                if name:
                    names.append(name)
        return [_violation(self, content, name, f"Name must match {pattern.pattern}.") for name in names if not pattern.fullmatch(document.text(name))]


class ConstantNameRule(BaseRule):
    rule_id = "IR-constant-name"
    description = "Use UPPER_SNAKE_CASE for configured static-final constant declarations."
    category = "naming"
    is_fixable = "no"
    default_config = {"severity": "warning", "pattern": r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*", "ignored_names": ["serialVersionUID"]}
    config_options = {
        **WARNING_OPTION,
        "pattern": {"default": r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*", "description": "Allowed constant-name pattern."},
        "ignored_names": {"default": ["serialVersionUID"], "description": "Static-final field names exempt from the rule."},
    }
    cases = [
        RuleCase("camel constant", "class Sample { static final int maxCount = 3; }\n", "reported"),
        RuleCase("snake constant", "class Sample { static final int MAX_COUNT = 3; }\n", "accepted"),
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        pattern = re.compile(str(rule_config.get("pattern", self.default_config["pattern"])))
        ignored = set(rule_config.get("ignored_names", self.default_config["ignored_names"]))
        violations = []
        for field in nodes_of_type(document, "field_declaration"):
            modifiers = next((child for child in field.children if child.type == "modifiers"), None)
            if not modifiers or not {"static", "final"}.issubset({child.type for child in modifiers.children}):
                continue
            for declarator in (child for child in field.named_children if child.type == "variable_declarator"):
                name = declarator.child_by_field_name("name")
                if name and document.text(name) not in ignored and not pattern.fullmatch(document.text(name)):
                    violations.append(_violation(self, content, name, f"Constant name must match {pattern.pattern}."))
        return violations


class PackageNameRule(BaseRule):
    rule_id = "IR-package-name"
    description = "Use lowercase alphanumeric Java package components."
    category = "naming"
    is_fixable = "no"
    default_config = WARNING_CONFIG
    config_options = WARNING_OPTION
    cases = [
        RuleCase("uppercase package", "package sample.App;\nclass Sample {}\n", "reported"),
        RuleCase("lowercase package", "package sample.app;\nclass Sample {}\n", "accepted"),
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        violations = []
        for node in nodes_of_type(document, "package_declaration"):
            name = document.text(node).removeprefix("package").removesuffix(";").strip()
            if not re.fullmatch(r"[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)*", name):
                violations.append(_violation(self, content, node, "Use lowercase package components."))
        return violations


class OverloadGroupingRule(BaseRule):
    rule_id = "IR-overload-grouping"
    description = "Keep methods and constructors with the same name in contiguous groups."
    category = "methods"
    is_fixable = "no"
    default_config = WARNING_CONFIG
    config_options = WARNING_OPTION
    cases = [
        RuleCase(
            "split overloads",
            "class Sample { void run() {} void pause() {} void run(int count) {} }\n",
            "reported",
        ),
        RuleCase(
            "grouped overloads",
            "class Sample { void run() {} void run(int count) {} void pause() {} }\n",
            "accepted",
        ),
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        violations = []
        body_types = {"class_body", "interface_body", "enum_body", "annotation_type_body"}
        for body in (node for node in walk(document.root) if node.type in body_types):
            declarations = [child for child in body.named_children if child.type in {"method_declaration", "constructor_declaration"}]
            names = []
            for declaration in declarations:
                name = declaration.child_by_field_name("name")
                names.append(document.text(name) if name else "<constructor>")
            last = {}
            for index, (declaration, name) in enumerate(zip(declarations, names)):
                if name in last and index - last[name] > 1:
                    violations.append(_violation(self, content, declaration, f"Keep overloads of {name} together."))
                last[name] = index
        return violations


class SwitchFallthroughRule(BaseRule):
    rule_id = "IR-switch-fallthrough"
    description = "Mark intentional fall-through in colon-style switch statement groups."
    category = "control-flow"
    is_fixable = "no"
    default_config = WARNING_CONFIG
    config_options = WARNING_OPTION
    cases = [
        RuleCase(
            "unmarked fallthrough",
            "class Sample { void run(int value) { switch (value) { case 1: prepare(); case 2: execute(); break; } } void prepare() {} void execute() {} }\n",
            "reported",
        ),
        RuleCase(
            "terminated group",
            "class Sample { void run(int value) { switch (value) { case 1: prepare(); break; case 2: execute(); break; } } void prepare() {} void execute() {} }\n",
            "accepted",
        ),
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        violations = []
        for block in nodes_of_type(document, "switch_block"):
            groups = [child for child in block.named_children if child.type == "switch_block_statement_group"]
            for group in groups[:-1]:
                text = document.text(group)
                if re.search(r"\b(break|continue|return|throw)\b[^;]*;\s*$", text, re.DOTALL):
                    continue
                if re.search(r"(?i)fall[ -]?through", text):
                    continue
                violations.append(_violation(self, content, group, "Add a fall-through comment or terminate the switch group."))
        return violations


class PublicApiJavadocRule(BaseRule):
    rule_id = "IR-public-api-javadoc"
    description = "Document public and protected top-level types and members."
    category = "documentation"
    is_fixable = "no"
    enabled_by_default = False
    default_config = WARNING_CONFIG
    config_options = WARNING_OPTION
    cases = [
        RuleCase("undocumented public type", "public class Sample {}\n", "reported"),
        RuleCase("documented public type", "/** Generic sample type. */\npublic class Sample {}\n", "accepted"),
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        violations = []
        declarations = {
            "class_declaration", "interface_declaration", "enum_declaration", "record_declaration",
            "annotation_type_declaration", "method_declaration", "constructor_declaration", "field_declaration",
        }
        for node in walk(document.root):
            if node.type not in declarations:
                continue
            modifiers = next((child for child in node.children if child.type == "modifiers"), None)
            if not modifiers or not {child.type for child in modifiers.children}.intersection({"public", "protected"}):
                continue
            previous = node.prev_named_sibling
            if not previous or previous.type != "block_comment" or not document.text(previous).startswith("/**"):
                violations.append(_violation(self, content, node, "Add Javadoc for the public API declaration."))
        return violations


class JavadocPlacementRule(BaseRule):
    rule_id = "IR-javadoc-placement"
    description = "Place Javadoc before declaration annotations."
    category = "documentation"
    is_fixable = "no"
    default_config = WARNING_CONFIG
    config_options = WARNING_OPTION
    cases = [
        RuleCase("Javadoc after annotation", "@Deprecated\n/** Old type. */\nclass Sample {}\n", "reported"),
        RuleCase("Javadoc before annotation", "/** Old type. */\n@Deprecated\nclass Sample {}\n", "accepted"),
    ]
    BAD = re.compile(r"(?m)^(?P<indent>[ \t]*)@[\w.]+(?:\([^\n]*\))?\s*\n(?P=indent)/\*\*")

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        lines = content.splitlines()
        return [
            Violation(self.rule_id, content.count("\n", 0, match.start()) + 2, "Move Javadoc before annotations.", [lines[content.count("\n", 0, match.start()) + 1]], False)
            for match in self.BAD.finditer(content)
        ]


class JavadocTagsRule(BaseRule):
    rule_id = "IR-javadoc-tags"
    description = "Use canonical Javadoc block-tag order and nonempty descriptions."
    category = "documentation"
    is_fixable = "no"
    default_config = WARNING_CONFIG
    config_options = WARNING_OPTION
    cases = [
        RuleCase("empty return tag", "/**\n * Value.\n * @return\n */\nclass Sample {}\n", "reported"),
        RuleCase("described return tag", "/**\n * Value.\n * @return the value\n */\nclass Sample {}\n", "accepted"),
    ]
    ORDER = {"param": 0, "return": 1, "throws": 2, "exception": 2, "deprecated": 3}

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        violations = []
        for node in nodes_of_type(document, "block_comment"):
            text = document.text(node)
            if not text.startswith("/**"):
                continue
            tags = re.findall(r"(?m)^\s*\*\s*@([a-z]+)(?:\s+([^\n*]+))?", text)
            ranks = [self.ORDER.get(tag, 99) for tag, _ in tags]
            if ranks != sorted(ranks) or any(tag in self.ORDER and not (description or "").strip() for tag, description in tags):
                violations.append(_violation(self, content, node, "Order Javadoc tags and give each tag a description."))
        return violations
