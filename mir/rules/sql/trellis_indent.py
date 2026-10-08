from typing import Any, Dict, List

from mir.engine.rule_interface import BaseRule, RuleCase, Violation
from mir.rules.sql.indent import IndentRule
from mir.rules.sql.sql_utils import find_matching_paren, tokenize_sql
from mir.rules.sql.trellis_utils import analyze_trellis, has_trellis_directives, parse_directive


class TrellisIndentRule(BaseRule):
    rule_id = "IR-trellis-indent"
    description = (
        "Indent Trellis blocks like programming-language control flow and align "
        "multiline parentheses within those blocks."
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
            "WHERE\n    item_id IN (\n        -- trellis: for item in item_ids separator=\",\"\n"
            "            :item\n        -- trellis: endfor\n    )",
        ),
        RuleCase(
            "directive layout aligns with its body",
            "VALUES (\n-- trellis: if optional_value\n"
            "    :optional_value\n-- trellis: endif\n)",
            "fixed",
            "VALUES (\n    -- trellis: if optional_value\n"
            "        :optional_value\n    -- trellis: endif\n)",
        ),
        RuleCase(
            "choose branches",
            "-- trellis: choose order\n-- trellis: when \"name\"\nORDER BY item_name\n"
            "-- trellis: otherwise\nORDER BY item_id\n-- trellis: endchoose",
            "fixed",
            "-- trellis: choose order\n    -- trellis: when \"name\"\n"
            "        ORDER BY item_name\n    -- trellis: otherwise\n"
            "        ORDER BY item_id\n-- trellis: endchoose",
        ),
    ]

    def _parenthesis_indents(self, content: str, indent_size: int) -> Dict[int, str]:
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

        expected = {}
        for line_number, line in enumerate(lines, 1):
            if not line.strip():
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

    @staticmethod
    def _deeper_indent(*values: str | None) -> str:
        return max((value for value in values if value is not None), key=len, default="")

    def _expected_indents(self, content: str, indent_size: int) -> Dict[int, str]:
        if not has_trellis_directives(content):
            return {}

        directives, issues, _ = analyze_trellis(content)
        parenthesis_indents = self._parenthesis_indents(content, indent_size)
        if issues:
            return {
                line_number: indentation
                for line_number, indentation in parenthesis_indents.items()
                if parse_directive(content.splitlines()[line_number - 1], line_number) is None
            }

        lines = content.splitlines()
        by_line = {directive.line: directive for directive in directives}
        expected: Dict[int, str] = {}
        stack: list[dict[str, str | None]] = []
        unit = " " * indent_size
        openers = {"if", "for", "choose"}
        closers = {"endif": "if", "endfor": "for", "endchoose": "choose"}

        for line_number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            directive = by_line.get(line_number)
            parent_body = stack[-1]["body"] if stack else None
            paren_indent = parenthesis_indents.get(line_number)
            if directive is None:
                required = self._deeper_indent(parent_body, paren_indent)
                if required:
                    expected[line_number] = required
                continue

            keyword = directive.keyword
            if keyword in openers:
                base = self._deeper_indent(parent_body, paren_indent)
                if not base:
                    base = directive.indent
                expected[line_number] = base
                body = None if keyword == "choose" else base + unit
                stack.append({"kind": keyword, "base": base, "body": body})
            elif keyword in {"elif", "else"} and stack:
                expected[line_number] = str(stack[-1]["base"])
                stack[-1]["body"] = str(stack[-1]["base"]) + unit
            elif keyword in {"when", "otherwise"} and stack:
                branch_indent = str(stack[-1]["base"]) + unit
                expected[line_number] = branch_indent
                stack[-1]["body"] = branch_indent + unit
            elif keyword in closers and stack:
                expected[line_number] = str(stack[-1]["base"])
                stack.pop()
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
            is_exact = line.lstrip().startswith(")") or parse_directive(line, line_number) is not None
            mismatch = actual != expected if is_exact else not actual.startswith(expected)
            if mismatch:
                violations.append(
                    Violation(
                        self.rule_id,
                        line_number,
                        "Align Trellis SQL and directives with their containing clause.",
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
        current = content
        for _ in range(10):
            expected = self._expected_indents(current, indent_size)
            if not expected:
                return current
            lines = current.splitlines()
            changed = False
            for line_number, indentation in expected.items():
                line = lines[line_number - 1]
                actual = line[: len(line) - len(line.lstrip())]
                is_exact = line.lstrip().startswith(")") or parse_directive(line, line_number) is not None
                mismatch = actual != indentation if is_exact else not actual.startswith(indentation)
                if mismatch:
                    lines[line_number - 1] = indentation + line.lstrip()
                    changed = True
            if not changed:
                return current
            current = "\n".join(lines) + ("\n" if current.endswith("\n") else "")
        return current
