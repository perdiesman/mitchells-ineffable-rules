"""Syntax-only Java correctness and policy checks."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from mir.engine.rule_interface import BaseRule, RuleCase, Violation
from mir.rules.java.java_utils import nodes_of_type, parse_java, walk


WARNING_CONFIG = {"severity": "warning"}
WARNING_OPTION = {"severity": {"default": "warning", "description": "Violation severity."}}


def _violation(rule: BaseRule, content: str, node, message: str) -> Violation:
    line = node.start_point.row + 1
    lines = content.splitlines()
    return Violation(rule.rule_id, line, message, [lines[line - 1]] if line <= len(lines) else [], False)


def _crosses_nested_boundary(node, ancestor) -> bool:
    current = node.parent
    while current is not None and current != ancestor:
        if current.type in {
            "lambda_expression",
            "method_declaration",
            "constructor_declaration",
            "class_declaration",
            "interface_declaration",
            "enum_declaration",
            "record_declaration",
        }:
            return True
        current = current.parent
    return current != ancestor


class FinallyControlFlowRule(BaseRule):
    rule_id = "IR-finally-control-flow"
    description = "Do not abruptly return, throw, break, or continue from a finally block."
    category = "correctness"
    is_fixable = "no"
    default_config = WARNING_CONFIG
    config_options = WARNING_OPTION
    cases = [
        RuleCase(
            "return from finally",
            "class Sample { int read() { try { return 1; } finally { return 2; } } }\n",
            "reported",
        ),
        RuleCase(
            "ordinary cleanup",
            "class Sample { int read() { try { return 1; } finally { cleanup(); } } void cleanup() {} }\n",
            "accepted",
        ),
        RuleCase(
            "nested lambda return",
            "class Sample { void read() { try {} finally { Runnable value = () -> { return; }; } } }\n",
            "accepted",
        ),
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        violations = []
        for clause in nodes_of_type(document, "finally_clause"):
            for node in walk(clause):
                if node.type not in {"return_statement", "throw_statement", "break_statement", "continue_statement"}:
                    continue
                if not _crosses_nested_boundary(node, clause):
                    violations.append(_violation(self, content, node, "Avoid abrupt control flow from finally."))
        return violations


class EqualsHashCodeRule(BaseRule):
    rule_id = "IR-equals-hash-code"
    description = "Declare equals and hashCode together in concrete Java classes."
    category = "correctness"
    is_fixable = "no"
    default_config = WARNING_CONFIG
    config_options = WARNING_OPTION
    cases = [
        RuleCase(
            "equals without hash code",
            "class Sample { public boolean equals(Object value) { return false; } }\n",
            "reported",
        ),
        RuleCase(
            "complete equality contract",
            "class Sample { public boolean equals(Object value) { return false; } public int hashCode() { return 1; } }\n",
            "accepted",
        ),
    ]

    @staticmethod
    def _method_names(document, body) -> set[str]:
        names = set()
        for child in body.named_children:
            if child.type != "method_declaration":
                continue
            name = child.child_by_field_name("name")
            parameters = child.child_by_field_name("parameters")
            if not name or not parameters:
                continue
            text = document.text(name)
            count = len(parameters.named_children)
            if (text == "equals" and count == 1) or (text == "hashCode" and count == 0):
                names.add(text)
        return names

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        violations = []
        for declaration in nodes_of_type(document, "class_declaration"):
            body = declaration.child_by_field_name("body")
            if not body:
                continue
            names = self._method_names(document, body)
            if len(names) == 1:
                missing = "hashCode" if "equals" in names else "equals"
                violations.append(_violation(self, content, declaration, f"Declare {missing} together with the equality contract."))
        return violations


class InterruptedExceptionRule(BaseRule):
    rule_id = "IR-interrupted-exception"
    description = "Propagate InterruptedException or visibly restore the thread interruption flag."
    category = "correctness"
    is_fixable = "no"
    enabled_by_default = False
    default_config = WARNING_CONFIG
    config_options = WARNING_OPTION
    cases = [
        RuleCase(
            "swallowed interruption",
            "class Sample { void waitForWork() { try { run(); } catch (InterruptedException exception) { log(exception); } } void run() throws InterruptedException {} void log(Exception value) {} }\n",
            "reported",
        ),
        RuleCase(
            "restored interruption",
            "class Sample { void waitForWork() { try { run(); } catch (InterruptedException exception) { Thread.currentThread().interrupt(); } } void run() throws InterruptedException {} }\n",
            "accepted",
        ),
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        violations = []
        for clause in nodes_of_type(document, "catch_clause"):
            parameter = next((child for child in clause.named_children if child.type == "catch_formal_parameter"), None)
            body = next((child for child in clause.named_children if child.type == "block"), None)
            if not parameter or not body or "InterruptedException" not in document.text(parameter):
                continue
            propagates = any(node.type == "throw_statement" for node in walk(body))
            restores = any(
                node.type == "method_invocation" and "Thread.currentThread().interrupt()" in "".join(document.text(node).split())
                for node in walk(body)
            )
            if not propagates and not restores:
                violations.append(_violation(self, content, clause, "Propagate the interruption or call Thread.currentThread().interrupt()."))
        return violations


class ConsoleOutputRule(BaseRule):
    rule_id = "IR-console-output"
    description = "Use project logging instead of console output or printStackTrace."
    category = "correctness"
    is_fixable = "no"
    enabled_by_default = False
    default_config = WARNING_CONFIG
    config_options = WARNING_OPTION
    cases = [
        RuleCase("standard output", "class Sample { void run() { System.out.println(\"value\"); } }\n", "reported"),
        RuleCase("print stack trace", "class Sample { void run(Exception problem) { problem.printStackTrace(); } }\n", "reported"),
        RuleCase("ordinary call", "class Sample { void run() { logger.info(\"value\"); } Object logger; }\n", "accepted"),
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        violations = []
        for node in nodes_of_type(document, "method_invocation"):
            text = "".join(document.text(node).split())
            if text.startswith(("System.out.", "System.err.")) or ".printStackTrace(" in text:
                violations.append(_violation(self, content, node, "Use the configured logging abstraction."))
        return violations


class JavadocCompletenessRule(BaseRule):
    rule_id = "IR-javadoc-completeness"
    description = "Keep existing public API Javadoc tags synchronized with method parameters, returns, and throws clauses."
    category = "documentation"
    is_fixable = "no"
    enabled_by_default = False
    default_config = WARNING_CONFIG
    config_options = WARNING_OPTION
    cases = [
        RuleCase(
            "missing parameter tag",
            "/** Returns a value.\n * @return the value\n */\npublic class Sample {\n    /** Reads a value.\n     * @return the value\n     */\n    public int read(String name) { return 1; }\n}\n",
            "reported",
        ),
        RuleCase(
            "complete method tags",
            "public class Sample {\n    /** Reads a value.\n     * @param name requested name\n     * @return the value\n     */\n    public int read(String name) { return 1; }\n}\n",
            "accepted",
        ),
    ]

    @staticmethod
    def _is_public_api(node) -> bool:
        modifiers = next((child for child in node.children if child.type == "modifiers"), None)
        return bool(modifiers and {child.type for child in modifiers.children}.intersection({"public", "protected"}))

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        violations = []
        for method in nodes_of_type(document, "method_declaration"):
            if not self._is_public_api(method):
                continue
            comment = method.prev_named_sibling
            if not comment or comment.type != "block_comment" or not document.text(comment).startswith("/**"):
                continue
            javadoc = document.text(comment)
            parameter_tags = set(re.findall(r"(?m)^\s*\*\s*@param\s+(?:<[^>]+>|([A-Za-z_$][\w$]*))", javadoc))
            parameter_tags.discard("")
            parameters = method.child_by_field_name("parameters")
            names = {
                document.text(name)
                for parameter in (parameters.named_children if parameters else [])
                if (name := parameter.child_by_field_name("name")) is not None
            }
            missing = sorted(names - parameter_tags)
            return_type = method.child_by_field_name("type")
            if missing:
                violations.append(_violation(self, content, method, "Document parameters: " + ", ".join(missing) + "."))
            if return_type and document.text(return_type) != "void" and not re.search(r"(?m)^\s*\*\s*@return\b", javadoc):
                violations.append(_violation(self, content, method, "Document the return value."))
            throws = next((child for child in method.named_children if child.type == "throws"), None)
            if throws:
                documented = set(re.findall(r"(?m)^\s*\*\s*@(?:throws|exception)\s+([\w.$]+)", javadoc))
                declared = {document.text(child).split(".")[-1] for child in throws.named_children}
                missing_throws = sorted(name for name in declared if name not in documented)
                if missing_throws:
                    violations.append(_violation(self, content, method, "Document thrown types: " + ", ".join(missing_throws) + "."))
        return violations


class DisabledTestReasonRule(BaseRule):
    rule_id = "IR-disabled-test-reason"
    description = "Give disabled JUnit tests a nonempty reason."
    category = "documentation"
    is_fixable = "no"
    enabled_by_default = False
    default_config = WARNING_CONFIG
    config_options = WARNING_OPTION
    cases = [
        RuleCase("missing disabled reason", "class SampleTest { @Disabled void waits() {} }\n", "reported"),
        RuleCase("documented disabled test", "class SampleTest { @Disabled(\"Waiting for replacement\") void waits() {} }\n", "accepted"),
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        violations = []
        for node in nodes_of_type(document, "marker_annotation", "annotation"):
            text = document.text(node).strip()
            name = text[1:].split("(", 1)[0].split(".")[-1]
            if name != "Disabled":
                continue
            if node.type == "marker_annotation" or not re.search(r"\(\s*\"[^\"]+\"\s*\)$", text, re.DOTALL):
                violations.append(_violation(self, content, node, "Explain why the test is disabled."))
        return violations


class ForbiddenApiRule(BaseRule):
    rule_id = "IR-forbidden-api"
    description = "Report explicitly configured Java imports, qualified references, and invocations."
    category = "correctness"
    is_fixable = "no"
    enabled_by_default = False
    default_config = {"severity": "warning", "symbols": ["System.gc"]}
    config_options = {
        **WARNING_OPTION,
        "symbols": {
            "default": ["System.gc"],
            "description": "Exact import names or qualified source references to report.",
        },
    }
    cases = [
        RuleCase("forbidden collection", "class Sample { void clean() { System.gc(); } }\n", "reported"),
        RuleCase("ordinary collection", "class Sample { void clean() { cleaner.run(); } Object cleaner; }\n", "accepted"),
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        document = parse_java(content)
        symbols = {str(value) for value in rule_config.get("symbols", self.default_config["symbols"])}
        if not symbols:
            return []
        violations = []
        candidates = {"import_declaration", "method_invocation", "field_access", "object_creation_expression"}
        claimed = set()
        for node in walk(document.root):
            if node.type not in candidates:
                continue
            text = "".join(document.text(node).split())
            for symbol in symbols:
                normalized = "".join(symbol.split())
                if normalized and (text == normalized or text.startswith(normalized + "(") or normalized in text):
                    key = (node.start_byte, symbol)
                    if key not in claimed:
                        claimed.add(key)
                        violations.append(_violation(self, content, node, f"Avoid configured forbidden API: {symbol}."))
                    break
        return violations
