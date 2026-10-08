from typing import Any, Dict, List

from mir.engine.rule_interface import BaseRule, RuleCase, Violation
from mir.rules.sql.indent import IndentRule
from mir.rules.sql.sql_utils import find_matching_paren, tokenize_sql
from mir.rules.sql.trellis_utils import has_trellis_directives, parse_directive


class TrellisIndentRule(BaseRule):
    rule_id = "IR-trellis-indent"
    description = (
        "Indent SQL inside directive-controlled multiline parentheses one level "
        "without moving Trellis comments."
    )
    category = "templates"
    is_fixable = "yes"
    enabled_by_default = True
    commit_profile = True
    trellis_safe = True

    default_config = {"indent_size": 4}
    config_options = {
        "indent_size": {
            "default": 4,
            "description": "Spaces added inside a multiline parenthesized expression.",
            "fallback": "IR-indent:indent_size",
        }
    }
    examples = []
    additional_validations = []
    cases = [
        RuleCase(
            "directive-controlled collection",
            "WHERE\n    item_id IN (\n-- trellis: for item in item_ids separator=\",\"\n"
            "  :item\n-- trellis: endfor\n  )",
            "fixed",
            "WHERE\n    item_id IN (\n-- trellis: for item in item_ids separator=\",\"\n"
            "        :item\n-- trellis: endfor\n    )",
        ),
        RuleCase(
            "directive layout remains unchanged",
            "VALUES (\n    -- trellis: if optional_value\n"
            "    :optional_value\n    -- trellis: endif\n)",
            "accepted",
        ),
    ]

    def _expected_indents(self, content: str, indent_size: int) -> Dict[int, str]:
        if not has_trellis_directives(content):
            return {}

        tokens = tokenize_sql(content)
        lines = content.splitlines()
        multiline_parens = []
        for index, token in enumerate(tokens):
            if token["type"] != "PAREN" or token["value"] != "(":
                continue
            close_index = find_matching_paren(tokens, index)
            if close_index is None:
                continue
            close_token = tokens[close_index]
            if token["line"] >= close_token["line"]:
                continue
            next_active = next(
                (
                    candidate
                    for candidate in tokens[index + 1 : close_index]
                    if candidate["type"] not in {"WHITESPACE", "COMMENT"}
                ),
                None,
            )
            if (
                next_active
                and next_active["type"] == "KEYWORD"
                and next_active["value"].upper() in {"SELECT", "WITH"}
            ):
                continue
            open_line = lines[token["line"] - 1]
            open_indent = open_line[: len(open_line) - len(open_line.lstrip())]
            multiline_parens.append((index, token, close_token, open_indent))

        expected: Dict[int, str] = {}
        for line_number, line in enumerate(lines, 1):
            if not line.strip() or parse_directive(line, line_number) is not None:
                continue
            active = [
                item
                for item in multiline_parens
                if item[1]["line"] < line_number <= item[2]["line"]
            ]
            if not active:
                continue
            _, _, close_token, open_indent = max(active, key=lambda item: item[0])
            expected[line_number] = (
                open_indent
                if line_number == close_token["line"] and line.lstrip().startswith(")")
                else open_indent + (" " * indent_size)
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
            is_closer = line.lstrip().startswith(")")
            mismatch = actual != expected if is_closer else not actual.startswith(expected)
            if mismatch:
                violations.append(
                    Violation(
                        self.rule_id,
                        line_number,
                        "Indent parenthesized Trellis SQL relative to its containing clause.",
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
        expected = self._expected_indents(content, indent_size)
        if not expected:
            return content
        lines = content.splitlines()
        for line_number, indentation in expected.items():
            line = lines[line_number - 1]
            actual = line[: len(line) - len(line.lstrip())]
            is_closer = line.lstrip().startswith(")")
            mismatch = actual != indentation if is_closer else not actual.startswith(indentation)
            if mismatch:
                lines[line_number - 1] = indentation + line.lstrip()
        return "\n".join(lines) + ("\n" if content.endswith("\n") else "")
