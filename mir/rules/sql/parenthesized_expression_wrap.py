from typing import Any, Dict, List

from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.line_length import LineLengthRule
from mir.rules.sql.sql_utils import find_matching_paren, source_text_length, tokenize_sql


class ParenthesizedExpressionWrapRule(BaseRule):
    commit_profile = True
    embedded_safe = True
    rule_id = "IR-parenthesized-expression-wrap"
    description = (
        "Long parenthesized arithmetic expressions should put each operand on "
        "an aligned continuation line and expand complex denominator calls."
    )
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {"max_line_length": 120}
    config_options = {
        "max_line_length": {
            "default": 120,
            "description": "Line length threshold for expanding the expression.",
            "fallback": "IR-line-length:max_length",
        }
    }

    examples = [
        {
            "violating": (
                "                (coalesce(max(current_outage), 0)::NUMERIC / "
                "greatest(coalesce(sum(normal_value * county_percent), 1)::INTEGER, 1)) "
                "- 1 AS outage_count"
            ),
            "correct": (
                "                (\n"
                "                    coalesce(max(current_outage), 0)::NUMERIC\n"
                "                    / greatest(\n"
                "                        coalesce(\n"
                "                            sum(normal_value * county_percent),\n"
                "                            1\n"
                "                        )::INTEGER,\n"
                "                        1\n"
                "                    )\n"
                "                ) - 1 AS outage_count"
            ),
        },
        {
            "violating": (
                "(\n"
                "    current_measure / expected_measure -\n"
                "    previous_measure_with_a_long_identifier / expected_measure\n"
                ")"
            ),
            "correct": (
                "(\n"
                "    current_measure / expected_measure\n"
                "    - previous_measure_with_a_long_identifier / expected_measure\n"
                ")"
            ),
        },
    ]
    additional_validations = [
        "SELECT (current_count / expected_count) AS ratio;",
        "SELECT (current_count + expected_count) AS total;",
    ]

    @staticmethod
    def _whitespace_before(tokens: List[dict], index: int) -> dict | None:
        if index > 0 and tokens[index - 1]["type"] == "WHITESPACE":
            return tokens[index - 1]
        return None

    @staticmethod
    def _whitespace_after(tokens: List[dict], index: int) -> dict | None:
        if index + 1 < len(tokens) and tokens[index + 1]["type"] == "WHITESPACE":
            return tokens[index + 1]
        return None

    def _find_edits(self, content: str, rule_config: Dict[str, Any]) -> List[dict]:
        max_length = self.get_config_value(
            rule_config,
            "max_line_length",
            120,
            fallbacks=[(LineLengthRule, "max_length")],
        )
        tokens = tokenize_sql(content)
        lines = content.splitlines()
        from mir.rules.sql.additive_wrap import AdditiveWrapRule
        expression_max_length = AdditiveWrapRule().get_config_value(
            rule_config,
            "max_line_length",
            default_value=100,
        )
        edits: List[dict] = []
        first_active_by_line: Dict[int, int] = {}
        for index, item in enumerate(tokens):
            if item["type"] not in ("WHITESPACE", "COMMENT"):
                first_active_by_line.setdefault(item["line"], index)

        def add_whitespace_edit(
            token_index: int,
            replacement: str,
            *,
            before: bool,
        ) -> None:
            whitespace = (
                self._whitespace_before(tokens, token_index)
                if before
                else self._whitespace_after(tokens, token_index)
            )
            token = tokens[token_index]
            start = (
                whitespace["start"]
                if whitespace
                else (token["start"] if before else token["end"])
            )
            end = (
                whitespace["end"]
                if whitespace
                else (token["start"] if before else token["end"])
            )
            if content[start:end] != replacement:
                edits.append(
                    {
                        "token": token,
                        "start": start,
                        "end": end,
                        "replacement": replacement,
                    }
                )

        def direct_commas(open_index: int, close_index: int) -> List[int]:
            depth = 0
            result = []
            for candidate in range(open_index + 1, close_index):
                item = tokens[candidate]
                if item["type"] == "PAREN":
                    depth += 1 if item["value"] == "(" else -1
                elif item["type"] == "COMMA" and depth == 0:
                    result.append(candidate)
            return result

        def expand_call(open_index: int, call_indent: str) -> None:
            close_index = find_matching_paren(tokens, open_index)
            if close_index is None:
                return
            commas = direct_commas(open_index, close_index)
            if not commas:
                return
            argument_indent = call_indent + "    "
            add_whitespace_edit(
                open_index, "\n" + argument_indent, before=False
            )
            for comma_index in commas:
                add_whitespace_edit(
                    comma_index, "\n" + argument_indent, before=False
                )
            add_whitespace_edit(close_index, "\n" + call_indent, before=True)

            argument_starts = [open_index + 1] + [index + 1 for index in commas]
            argument_ends = commas + [close_index]
            for start, end in zip(argument_starts, argument_ends):
                active = [
                    index
                    for index in range(start, end)
                    if tokens[index]["type"] not in ("WHITESPACE", "COMMENT")
                ]
                if len(active) < 2:
                    continue
                name_index = active[0]
                nested_open = active[1]
                if (
                    tokens[name_index]["type"] in ("IDENTIFIER", "KEYWORD")
                    and tokens[nested_open]["type"] == "PAREN"
                    and tokens[nested_open]["value"] == "("
                ):
                    expand_call(nested_open, argument_indent)

        for open_index, token in enumerate(tokens):
            if token["type"] != "PAREN" or token["value"] != "(":
                continue
            line_index = token["line"] - 1
            if line_index >= len(lines):
                continue
            line = lines[line_index]
            first_on_line = first_active_by_line.get(token["line"])
            if first_on_line != open_index:
                continue
            close_index = find_matching_paren(tokens, open_index)
            if close_index is None:
                continue

            if tokens[close_index]["line"] != token["line"]:
                first_inner_active = next(
                    (
                        tokens[candidate]
                        for candidate in range(open_index + 1, close_index)
                        if tokens[candidate]["type"]
                        not in ("WHITESPACE", "COMMENT")
                    ),
                    None,
                )
                if (
                    first_inner_active is not None
                    and first_inner_active["type"] == "KEYWORD"
                    and first_inner_active["value"].upper()
                    in {"SELECT", "WITH"}
                ):
                    # Query-block parentheses own many unrelated arithmetic
                    # expressions. Each expression must be formatted in its
                    # own local context rather than as one outer arithmetic
                    # group.
                    continue
                base_indent = line[: len(line) - len(line.lstrip(" \t"))]
                content_indent = base_indent + "    "
                depth = 0
                operators = []
                for candidate in range(open_index + 1, close_index):
                    item = tokens[candidate]
                    if item["type"] == "PAREN":
                        depth += 1 if item["value"] == "(" else -1
                    elif (
                        depth == 0
                        and item["type"] == "OPERATOR"
                        and item["value"] in {"+", "-", "*", "/", "||"}
                    ):
                        operators.append(candidate)
                trailing_operator_lines = set()
                for operator_index in operators:
                    next_active_index = next(
                        (
                            candidate
                            for candidate in range(operator_index + 1, close_index)
                            if tokens[candidate]["type"]
                            not in ("WHITESPACE", "COMMENT")
                        ),
                        None,
                    )
                    if (
                        next_active_index is not None
                        and tokens[next_active_index]["line"]
                        > tokens[operator_index]["line"]
                    ):
                        trailing_operator_lines.add(tokens[operator_index]["line"])
                for operator_index in operators:
                    operator = tokens[operator_index]
                    previous_on_line = first_active_by_line.get(operator["line"])
                    next_active_index = next(
                        (
                            candidate
                            for candidate in range(operator_index + 1, close_index)
                            if tokens[candidate]["type"]
                            not in ("WHITESPACE", "COMMENT")
                        ),
                        None,
                    )
                    trails_line = bool(
                        next_active_index is not None
                        and tokens[next_active_index]["line"] > operator["line"]
                    )
                    operator_line = lines[operator["line"] - 1]
                    line_is_long = (
                        source_text_length(operator_line, rule_config)
                        > expression_max_length
                    )
                    if previous_on_line == operator_index:
                        continue
                    if trails_line:
                        add_whitespace_edit(
                            operator_index,
                            "\n" + content_indent,
                            before=True,
                        )
                        add_whitespace_edit(
                            operator_index,
                            " ",
                            before=False,
                        )
                    elif (
                        line_is_long
                        and operator["line"] not in trailing_operator_lines
                    ):
                        add_whitespace_edit(
                            operator_index,
                            "\n" + content_indent,
                            before=True,
                        )
                continue

            if source_text_length(line, rule_config) <= max_length:
                continue

            depth = 0
            operators = []
            for candidate in range(open_index + 1, close_index):
                item = tokens[candidate]
                if item["type"] == "PAREN":
                    depth += 1 if item["value"] == "(" else -1
                elif (
                    depth == 0
                    and item["type"] == "OPERATOR"
                    and item["value"] in {"+", "-", "*", "/", "||"}
                ):
                    operators.append(candidate)
            if not operators:
                continue

            base_indent = line[: len(line) - len(line.lstrip(" \t"))]
            content_indent = base_indent + "    "
            add_whitespace_edit(open_index, "\n" + content_indent, before=False)
            for operator_index in operators:
                add_whitespace_edit(
                    operator_index, "\n" + content_indent, before=True
                )
            add_whitespace_edit(close_index, "\n" + base_indent, before=True)

            for operator_index in operators:
                if tokens[operator_index]["value"] != "/":
                    continue
                name_index = next(
                    (
                        candidate
                        for candidate in range(operator_index + 1, close_index)
                        if tokens[candidate]["type"]
                        not in ("WHITESPACE", "COMMENT")
                    ),
                    None,
                )
                if name_index is None or tokens[name_index]["type"] not in (
                    "IDENTIFIER",
                    "KEYWORD",
                ):
                    continue
                denominator_open = next(
                    (
                        candidate
                        for candidate in range(name_index + 1, close_index)
                        if tokens[candidate]["type"]
                        not in ("WHITESPACE", "COMMENT")
                    ),
                    None,
                )
                if (
                    denominator_open is not None
                    and tokens[denominator_open]["type"] == "PAREN"
                    and tokens[denominator_open]["value"] == "("
                ):
                    expand_call(denominator_open, content_indent)

        unique = {
            (item["start"], item["end"]): item
            for item in edits
        }
        return list(unique.values())

    def check(
        self, content: str, file_path: str, rule_config: Dict[str, Any]
    ) -> List[Violation]:
        lines = content.splitlines()
        return [
            Violation(
                rule_id=self.rule_id,
                line_number=item["token"]["line"],
                message="Long parenthesized arithmetic expression should use aligned continuation lines.",
                offending_lines=[
                    lines[item["token"]["line"] - 1]
                    if item["token"]["line"] - 1 < len(lines)
                    else ""
                ],
                is_fixable=True,
            )
            for item in self._find_edits(content, rule_config)
        ]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        edits = self._find_edits(content, rule_config)
        chars = list(content)
        for item in sorted(edits, key=lambda edit: edit["start"], reverse=True):
            chars[item["start"]:item["end"]] = list(item["replacement"])
        return "".join(chars)
