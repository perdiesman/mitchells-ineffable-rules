from typing import Any, Dict, List

from mir.engine.rule_interface import BaseRule, RuleCase, Violation
from mir.rules.sql.indent import IndentRule
from mir.rules.sql.sql_utils import find_matching_paren, tokenize_sql


def table_function_parens(tokens: List[dict]) -> Dict[int, str]:
    """Return table-function opening parentheses and their source keywords."""
    active = [
        index
        for index, token in enumerate(tokens)
        if token["type"] not in {"WHITESPACE", "COMMENT"}
    ]
    active_position = {token_index: position for position, token_index in enumerate(active)}
    matches: Dict[int, str] = {}
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
            matches[token_index] = tokens[active[position]]["value"].upper()
    return matches


class TableFunctionIndentRule(BaseRule):
    commit_profile = True
    embedded_safe = True
    embedded_dynamic_indent_safe = True
    trellis_safe = True
    rule_id = "IR-table-function-indent"
    description = (
        "Indent multiline table-function arguments as table continuations, with "
        "joined functions nested beneath the JOIN."
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
            "multiline FROM table function",
            "FROM sample.items_for_period(\n        :period\n    ) AS item",
            "fixed",
            "FROM sample.items_for_period(\n    :period\n) AS item",
        ),
        RuleCase(
            "multiline JOIN table function",
            "    JOIN sample.items_for_period(\n        :period\n    ) AS item ON TRUE",
            "fixed",
            "    JOIN sample.items_for_period(\n            :period\n        ) AS item ON TRUE",
        ),
    ]

    def _expected_indents(self, content: str, indent_size: int) -> Dict[int, str]:
        tokens = tokenize_sql(content)
        lines = content.splitlines()
        ranges = []
        unit = " " * indent_size
        for open_index, source_keyword in table_function_parens(tokens).items():
            close_index = find_matching_paren(tokens, open_index)
            if close_index is None:
                continue
            opening = tokens[open_index]
            closing = tokens[close_index]
            if opening["line"] >= closing["line"]:
                continue
            opening_line = lines[opening["line"] - 1]
            opening_indent = opening_line[: len(opening_line) - len(opening_line.lstrip())]
            continuation_indent = opening_indent + (unit if source_keyword == "JOIN" else "")
            case_adjustments: Dict[int, int] = {}
            case_depth = 0
            seen_lines = set()
            for token_index in range(open_index + 1, close_index):
                token = tokens[token_index]
                if token["type"] in {"WHITESPACE", "COMMENT"}:
                    continue
                value = token["value"].upper()
                if token["line"] not in seen_lines:
                    adjustment = case_depth
                    if token["type"] == "KEYWORD" and value == "END":
                        adjustment = max(0, adjustment - 1)
                    case_adjustments[token["line"]] = adjustment
                    seen_lines.add(token["line"])
                if token["type"] == "KEYWORD" and value == "CASE":
                    case_depth += 1
                elif token["type"] == "KEYWORD" and value == "END":
                    case_depth = max(0, case_depth - 1)
            ranges.append(
                (open_index, opening, closing, continuation_indent, case_adjustments)
            )

        expected: Dict[int, str] = {}
        for line_number, line in enumerate(lines, 1):
            active = [
                item
                for item in ranges
                if item[1]["line"] < line_number <= item[2]["line"]
            ]
            if not active or not line.strip():
                continue
            _, _, closing, continuation_indent, case_adjustments = max(
                active, key=lambda item: item[0]
            )
            expected[line_number] = (
                continuation_indent
                if line_number == closing["line"] and line.lstrip().startswith(")")
                else continuation_indent
                + unit
                + unit * case_adjustments.get(line_number, 0)
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
