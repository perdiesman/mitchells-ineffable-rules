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
        "Keep a fitting table-function opener with its function name; otherwise "
        "indent multiline arguments as table continuations, with joined functions "
        "and their wrapped predicate expressions nested beneath the JOIN."
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
            "short multiline table function",
            (
                "FROM generate_series\n"
                "    (:period_start, :period_end, '15 MINUTES' :: interval) AS period"
            ),
            "fixed",
            (
                "FROM generate_series("
                ":period_start, :period_end, '15 MINUTES'::interval"
                ") AS period"
            ),
        ),
        RuleCase(
            "multiline JOIN table function",
            "    JOIN sample.items_for_period(\n        :period\n    ) AS item ON TRUE",
            "fixed",
            "    JOIN sample.items_for_period(\n            :period\n        ) AS item ON TRUE",
        ),
        RuleCase(
            "joined table function with additive predicate continuation",
            (
                "    JOIN sample.items_for_period(\n"
                "        :period\n"
                "    ) AS item ON event_time BETWEEN item.start_time AND item.start_time\n"
                "+ item.duration"
            ),
            "fixed",
            (
                "    JOIN sample.items_for_period(\n"
                "            :period\n"
                "        ) AS item ON event_time BETWEEN item.start_time AND item.start_time\n"
                "        + item.duration"
            ),
        ),
        RuleCase(
            "joined table function with multiline predicate",
            (
                "    LEFT JOIN sample.items_for_period(:period, :region) item\n"
                "        ON item.period_id = event.period_id\n"
                "        AND item.enabled"
            ),
            "fixed",
            (
                "    LEFT JOIN sample.items_for_period(\n"
                "            :period,\n"
                "            :region\n"
                "        ) item\n"
                "        ON item.period_id = event.period_id\n"
                "        AND item.enabled"
            ),
        ),
    ]

    @staticmethod
    def _compact_tokens(tokens: List[dict]) -> str:
        parts: List[str] = []
        previous = None
        pending_space = False
        for token in tokens:
            if token["type"] == "COMMENT":
                return ""
            if token["type"] == "WHITESPACE":
                pending_space = True
                continue
            value = token["value"]
            no_space_before = (
                token["type"] in {"COMMA", "DOT", "CAST"}
                or (token["type"] == "PAREN" and value == ")")
            )
            no_space_after_previous = bool(
                previous
                and (
                    previous["type"] in {"DOT", "CAST"}
                    or (
                        previous["type"] == "PAREN"
                        and previous["value"] == "("
                    )
                )
            )
            if pending_space and parts and not no_space_before and not no_space_after_previous:
                parts.append(" ")
            parts.append(value)
            pending_space = token["type"] == "COMMA"
            previous = token
        return "".join(parts).strip()

    def _compact_edits(
        self, content: str, rule_config: Dict[str, Any]
    ) -> List[dict]:
        tokens = tokenize_sql(content)
        lines = content.splitlines()
        max_length = self.get_config_value(
            rule_config,
            "max_length",
            120,
        )
        boundaries = rule_config.get("mybatis_boundary_offsets", set())
        edits = []
        for open_index, source_keyword in table_function_parens(tokens).items():
            close_index = find_matching_paren(tokens, open_index)
            if close_index is None:
                continue
            if (
                source_keyword == "JOIN"
                and self._multiline_join_predicate(tokens, close_index)
            ):
                continue
            opening = tokens[open_index]
            closing = tokens[close_index]
            whitespace_before = (
                tokens[open_index - 1]
                if open_index > 0
                and tokens[open_index - 1]["type"] == "WHITESPACE"
                else None
            )
            if not (
                whitespace_before
                and "\n" in whitespace_before["value"]
            ):
                continue
            edit_start = (
                whitespace_before["start"]
                if whitespace_before
                and "\n" in whitespace_before["value"]
                else opening["start"]
            )
            if any(edit_start < offset < closing["end"] for offset in boundaries):
                continue
            inner_tokens = tokens[open_index + 1 : close_index]
            nested_depth = 0
            has_multiple_arguments = False
            for token in inner_tokens:
                if token["type"] == "PAREN":
                    nested_depth += 1 if token["value"] == "(" else -1
                elif token["type"] == "COMMA" and nested_depth == 0:
                    has_multiple_arguments = True
                    break
            if not has_multiple_arguments:
                continue
            compact_inner = self._compact_tokens(inner_tokens)
            if not compact_inner:
                continue
            replacement = "(" + compact_inner + ")"
            line_start = content.rfind("\n", 0, edit_start) + 1
            line_end = content.find("\n", closing["end"])
            if line_end == -1:
                line_end = len(content)
            candidate = (
                content[line_start:edit_start]
                + replacement
                + content[closing["end"] : line_end]
            )
            if len(candidate) <= max_length:
                edits.append({
                    "token": opening,
                    "start": edit_start,
                    "end": closing["end"],
                    "replacement": replacement,
                })
        return edits

    @staticmethod
    def _multiline_join_predicate(
        tokens: List[dict], close_index: int
    ) -> bool:
        closing = tokens[close_index]
        on_token = None
        for token in tokens[close_index + 1:]:
            if token["type"] in {"WHITESPACE", "COMMENT"}:
                continue
            value = token["value"].upper()
            if token["type"] == "KEYWORD" and value in {
                "WHERE", "GROUP", "ORDER", "HAVING", "LIMIT", "JOIN",
            }:
                if value != "ON":
                    break
            if token["type"] == "KEYWORD" and value == "ON":
                on_token = token
                break
        if on_token is None:
            return False
        if on_token["line"] > closing["line"]:
            return True
        for token in tokens[close_index + 1:]:
            if token["type"] in {"WHITESPACE", "COMMENT"}:
                continue
            value = token["value"].upper()
            if token["type"] == "KEYWORD" and value in {
                "WHERE", "GROUP", "ORDER", "HAVING", "LIMIT", "JOIN",
            }:
                break
            if (
                token["type"] == "KEYWORD"
                and value in {"AND", "OR"}
                and token["line"] > on_token["line"]
            ):
                return True
        return False

    def _expand_join_edits(
        self, content: str, rule_config: Dict[str, Any]
    ) -> List[dict]:
        tokens = tokenize_sql(content)
        indent_size = self.get_config_value(
            rule_config,
            "indent_size",
            4,
            fallbacks=[(IndentRule, "indent_size")],
        )
        unit = " " * indent_size
        edits = []
        for open_index, source_keyword in table_function_parens(tokens).items():
            if source_keyword != "JOIN":
                continue
            close_index = find_matching_paren(tokens, open_index)
            if close_index is None:
                continue
            opening = tokens[open_index]
            closing = tokens[close_index]
            if (
                opening["line"] != closing["line"]
                or not self._multiline_join_predicate(tokens, close_index)
            ):
                continue
            argument_ranges = []
            range_start = open_index + 1
            nested_depth = 0
            for index in range(open_index + 1, close_index):
                token = tokens[index]
                if token["type"] == "PAREN":
                    nested_depth += 1 if token["value"] == "(" else -1
                elif token["type"] == "COMMA" and nested_depth == 0:
                    argument_ranges.append((range_start, index))
                    range_start = index + 1
            argument_ranges.append((range_start, close_index))
            if len(argument_ranges) < 2:
                continue
            arguments = [
                self._compact_tokens(tokens[start:end])
                for start, end in argument_ranges
            ]
            if not all(arguments):
                continue
            line_start = content.rfind("\n", 0, opening["start"]) + 1
            line = content[line_start:opening["start"]]
            base_indent = line[: len(line) - len(line.lstrip(" \t"))]
            close_indent = base_indent + unit
            argument_indent = close_indent + unit
            edits.append({
                "token": opening,
                "start": opening["start"],
                "end": closing["end"],
                "replacement": (
                    "(\n"
                    + argument_indent
                    + (",\n" + argument_indent).join(arguments)
                    + "\n"
                    + close_indent
                    + ")"
                ),
            })
        return edits

    def _multiline_argument_edits(
        self, content: str, rule_config: Dict[str, Any]
    ) -> List[dict]:
        """Put direct arguments and the close of a multiline call on their own lines."""
        tokens = tokenize_sql(content)
        indent_size = self.get_config_value(
            rule_config,
            "indent_size",
            4,
            fallbacks=[(IndentRule, "indent_size")],
        )
        unit = " " * indent_size
        edits = []

        def whitespace_edit(token_index: int, before: bool, expected: str) -> None:
            whitespace_index = token_index - 1 if before else token_index + 1
            whitespace = (
                tokens[whitespace_index]
                if 0 <= whitespace_index < len(tokens)
                and tokens[whitespace_index]["type"] == "WHITESPACE"
                else None
            )
            token = tokens[token_index]
            start = whitespace["start"] if whitespace else (
                token["start"] if before else token["end"]
            )
            end = whitespace["end"] if whitespace else start
            if content[start:end] != expected:
                edits.append({
                    "token": token,
                    "start": start,
                    "end": end,
                    "replacement": expected,
                })

        for open_index, source_keyword in table_function_parens(tokens).items():
            close_index = find_matching_paren(tokens, open_index)
            if close_index is None:
                continue
            opening = tokens[open_index]
            closing = tokens[close_index]
            if opening["line"] >= closing["line"]:
                continue
            line_start = content.rfind("\n", 0, opening["start"]) + 1
            line_prefix = content[line_start:opening["start"]]
            base_indent = line_prefix[: len(line_prefix) - len(line_prefix.lstrip())]
            close_indent = base_indent + (unit if source_keyword == "JOIN" else "")
            argument_indent = close_indent + unit
            whitespace_edit(open_index, False, "\n" + argument_indent)
            whitespace_edit(close_index, True, "\n" + close_indent)

            depth = 0
            for index in range(open_index + 1, close_index):
                token = tokens[index]
                if token["type"] == "PAREN":
                    depth += 1 if token["value"] == "(" else -1
                elif token["type"] == "COMMA" and depth == 0:
                    whitespace_edit(index, False, "\n" + argument_indent)
        return list({
            (item["start"], item["end"]): item for item in edits
        }.values())

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
        for _, _, closing, continuation_indent, _ in ranges:
            next_line_number = closing["line"] + 1
            if next_line_number > len(lines):
                continue
            closing_line = lines[closing["line"] - 1]
            next_line = lines[next_line_number - 1]
            if (
                " ON " in closing_line
                and next_line.lstrip().startswith(("+", "||"))
            ):
                expected[next_line_number] = continuation_indent
        return expected

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        indent_size = self.get_config_value(
            rule_config,
            "indent_size",
            4,
            fallbacks=[(IndentRule, "indent_size")],
        )
        lines = content.splitlines()
        violations = [
            Violation(
                self.rule_id,
                item["token"]["line"],
                "A table-function call that fits should remain on one line.",
                [lines[item["token"]["line"] - 1]],
                True,
            )
            for item in self._compact_edits(content, rule_config)
        ]
        violations.extend(
            Violation(
                self.rule_id,
                item["token"]["line"],
                "A joined table function with a multiline predicate should expand its arguments.",
                [lines[item["token"]["line"] - 1]],
                True,
            )
            for item in self._expand_join_edits(content, rule_config)
        )
        violations.extend(
            Violation(
                self.rule_id,
                item["token"]["line"],
                "Multiline table-function arguments must use one line each.",
                [lines[item["token"]["line"] - 1]],
                True,
            )
            for item in self._multiline_argument_edits(content, rule_config)
        )
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
        expand_edits = self._expand_join_edits(content, rule_config)
        if expand_edits:
            chars = list(content)
            for item in sorted(
                expand_edits, key=lambda edit: edit["start"], reverse=True
            ):
                chars[item["start"] : item["end"]] = list(item["replacement"])
            content = "".join(chars)
        argument_edits = self._multiline_argument_edits(content, rule_config)
        if argument_edits:
            chars = list(content)
            for item in sorted(
                argument_edits, key=lambda edit: edit["start"], reverse=True
            ):
                chars[item["start"] : item["end"]] = list(item["replacement"])
            content = "".join(chars)
        compact_edits = self._compact_edits(content, rule_config)
        if compact_edits:
            chars = list(content)
            for item in sorted(
                compact_edits, key=lambda edit: edit["start"], reverse=True
            ):
                chars[item["start"] : item["end"]] = list(item["replacement"])
            content = "".join(chars)
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
