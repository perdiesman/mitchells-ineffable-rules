from typing import Any, Dict, List

from mir.engine.rule_interface import BaseRule, RuleCase, Violation
from mir.rules.sql.indent import IndentRule
from mir.rules.sql.sql_utils import find_matching_paren, tokenize_sql


def table_function_parens(tokens: List[dict]) -> set[int]:
    """Return opening parentheses for qualified functions used as table sources."""
    active = [
        index
        for index, token in enumerate(tokens)
        if token["type"] not in {"WHITESPACE", "COMMENT"}
    ]
    active_position = {token_index: position for position, token_index in enumerate(active)}
    matches: set[int] = set()
    for token_index in active:
        token = tokens[token_index]
        if token["type"] != "PAREN" or token["value"] != "(":
            continue
        position = active_position[token_index] - 1
        if position < 0 or tokens[active[position]]["type"] != "IDENTIFIER":
            continue
        position -= 1
        while position >= 1 and tokens[active[position]]["type"] == "DOT":
            if tokens[active[position - 1]]["type"] != "IDENTIFIER":
                break
            position -= 2
        if position >= 0 and tokens[active[position]]["value"].upper() == "LATERAL":
            position -= 1
        if position >= 0 and tokens[active[position]]["value"].upper() in {"FROM", "JOIN"}:
            matches.add(token_index)
    return matches


class TableFunctionIndentRule(BaseRule):
    commit_profile = True
    embedded_safe = True
    trellis_safe = True
    rule_id = "IR-table-function-indent"
    description = (
        "Indent multiline table-function arguments one level below FROM or JOIN "
        "and align the closing parenthesis with the function call."
    )
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {"indent_size": 4}
    config_options = {
        "indent_size": {
            "default": 4,
            "description": "Spaces added inside a multiline table-function call.",
            "fallback": "IR-indent:indent_size",
        }
    }
    examples = []
    additional_validations = []
    cases = [
        RuleCase(
            "multiline table function",
            "FROM sample.items_for_period(\n        :period\n    ) AS item",
            "fixed",
            "FROM sample.items_for_period(\n    :period\n) AS item",
        )
    ]

    def _expected_indents(self, content: str, indent_size: int) -> Dict[int, str]:
        tokens = tokenize_sql(content)
        lines = content.splitlines()
        ranges = []
        for open_index in table_function_parens(tokens):
            close_index = find_matching_paren(tokens, open_index)
            if close_index is None:
                continue
            opening = tokens[open_index]
            closing = tokens[close_index]
            if opening["line"] >= closing["line"]:
                continue
            opening_line = lines[opening["line"] - 1]
            opening_indent = opening_line[: len(opening_line) - len(opening_line.lstrip())]
            ranges.append((open_index, opening, closing, opening_indent))

        expected: Dict[int, str] = {}
        unit = " " * indent_size
        for line_number, line in enumerate(lines, 1):
            active = [
                item
                for item in ranges
                if item[1]["line"] < line_number <= item[2]["line"]
            ]
            if not active or not line.strip():
                continue
            _, _, closing, opening_indent = max(active, key=lambda item: item[0])
            expected[line_number] = (
                opening_indent
                if line_number == closing["line"] and line.lstrip().startswith(")")
                else opening_indent + unit
            )
        return expected

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        indent_size = self.get_config_value(
            rule_config,
            "indent_size",
            4,
            fallbacks=[(IndentRule, "indent_size")],
        )
        lines = content.splitlines()
        violations = []
        for line_number, expected in self._expected_indents(content, indent_size).items():
            line = lines[line_number - 1]
            actual = line[: len(line) - len(line.lstrip())]
            if actual != expected:
                violations.append(
                    Violation(
                        self.rule_id,
                        line_number,
                        "Align multiline table-function contents with their FROM or JOIN clause.",
                        [line],
                        True,
                    )
                )
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        indent_size = self.get_config_value(
            rule_config,
            "indent_size",
            4,
            fallbacks=[(IndentRule, "indent_size")],
        )
        lines = content.splitlines()
        changed = False
        for line_number, expected in self._expected_indents(content, indent_size).items():
            line = lines[line_number - 1]
            actual = line[: len(line) - len(line.lstrip())]
            if actual != expected:
                lines[line_number - 1] = expected + line.lstrip()
                changed = True
        if not changed:
            return content
        ending = "\r\n" if "\r\n" in content else "\n"
        return ending.join(lines) + (ending if content.endswith(ending) else "")
