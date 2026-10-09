from typing import Any, Dict, List

from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import find_matching_paren, get_token_depths, tokenize_sql


class WindowLayoutRule(BaseRule):
    commit_profile = True
    embedded_safe = True
    rule_id = "IR-window-layout"
    description = (
        "Multiline window expressions should indent OVER clauses, place each "
        "PARTITION BY field on its own line, and align wrapper arguments."
    )
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {}
    config_options = {}

    examples = [
        {
            "violating": (
                "    coalesce(lag(item_count) OVER (\n"
                "        PARTITION BY item_type, item_region\n"
                "        ORDER BY recorded_at ASC\n"
                "    ), 0) AS prior_count"
            ),
            "correct": (
                "    coalesce(\n"
                "        lag(item_count) OVER (\n"
                "            PARTITION BY\n"
                "                item_type,\n"
                "                item_region\n"
                "            ORDER BY recorded_at ASC\n"
                "        ),\n"
                "        0\n"
                "    ) AS prior_count"
            ),
        }
    ]
    additional_validations = [
        "SELECT lag(item_count) OVER (ORDER BY recorded_at) FROM sample_item;"
    ]

    def _find_edits(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        lines = content.splitlines()
        stack = []
        enclosing = {}
        for index, token in enumerate(tokens):
            enclosing[index] = tuple(stack)
            if token["type"] == "PAREN" and token["value"] == "(":
                stack.append(index)
            elif token["type"] == "PAREN" and token["value"] == ")" and stack:
                stack.pop()

        edits = []

        def active_after(index: int, end: int) -> int | None:
            return next(
                (
                    candidate
                    for candidate in range(index + 1, end)
                    if tokens[candidate]["type"] not in ("WHITESPACE", "COMMENT")
                ),
                None,
            )

        def whitespace_edit(index: int, replacement: str, before: bool) -> None:
            whitespace_index = index - 1 if before else index + 1
            whitespace = (
                tokens[whitespace_index]
                if 0 <= whitespace_index < len(tokens)
                and tokens[whitespace_index]["type"] == "WHITESPACE"
                else None
            )
            token = tokens[index]
            start = whitespace["start"] if whitespace else (
                token["start"] if before else token["end"]
            )
            end = whitespace["end"] if whitespace else (
                token["start"] if before else token["end"]
            )
            if content[start:end] != replacement:
                edits.append({
                    "token": token,
                    "start": start,
                    "end": end,
                    "replacement": replacement,
                })

        for over_index, over_token in enumerate(tokens):
            if over_token["type"] != "KEYWORD" or over_token["value"].upper() != "OVER":
                continue
            over_open = active_after(over_index, len(tokens))
            if over_open is None or tokens[over_open]["value"] != "(":
                continue
            over_close = find_matching_paren(tokens, over_open)
            if over_close is None or tokens[over_close]["line"] == tokens[over_open]["line"]:
                continue

            wrapper_open = enclosing.get(over_index, ())[-1] if enclosing.get(over_index) else None
            if wrapper_open is None:
                continue
            wrapper_close = find_matching_paren(tokens, wrapper_open)
            if wrapper_close is None:
                continue
            wrapper_depth = depths[wrapper_open] + 1
            wrapper_commas = [
                index
                for index in range(wrapper_open + 1, wrapper_close)
                if tokens[index]["type"] == "COMMA" and depths[index] == wrapper_depth
            ]
            if not wrapper_commas:
                continue

            line = lines[tokens[wrapper_open]["line"] - 1]
            base_indent = line[: len(line) - len(line.lstrip(" \t"))]
            expression_indent = base_indent + "    "
            window_indent = expression_indent + "    "
            field_indent = window_indent + "    "

            whitespace_edit(wrapper_open, "\n" + expression_indent, before=False)
            for comma in wrapper_commas:
                whitespace_edit(comma, "\n" + expression_indent, before=False)
            whitespace_edit(wrapper_close, "\n" + base_indent, before=True)
            whitespace_edit(over_open, "\n" + window_indent, before=False)
            whitespace_edit(over_close, "\n" + expression_indent, before=True)

            over_depth = depths[over_open] + 1
            partition_index = next(
                (
                    index
                    for index in range(over_open + 1, over_close)
                    if depths[index] == over_depth
                    and tokens[index]["type"] == "KEYWORD"
                    and tokens[index]["value"].upper() == "PARTITION"
                ),
                None,
            )
            order_index = next(
                (
                    index
                    for index in range(over_open + 1, over_close)
                    if depths[index] == over_depth
                    and tokens[index]["type"] == "KEYWORD"
                    and tokens[index]["value"].upper() == "ORDER"
                ),
                None,
            )
            if partition_index is not None:
                by_index = active_after(partition_index, over_close)
                if (
                    by_index is not None
                    and tokens[by_index]["value"].upper() == "BY"
                ):
                    whitespace_edit(by_index, "\n" + field_indent, before=False)
                    partition_end = order_index or over_close
                    for index in range(by_index + 1, partition_end):
                        if tokens[index]["type"] == "COMMA" and depths[index] == over_depth:
                            whitespace_edit(index, "\n" + field_indent, before=False)
            if order_index is not None:
                whitespace_edit(order_index, "\n" + window_indent, before=True)

        return list({(item["start"], item["end"]): item for item in edits}.values())

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        lines = content.splitlines()
        return [
            Violation(
                rule_id=self.rule_id,
                line_number=item["token"]["line"],
                message="Multiline window expression should use aligned clause and field indentation.",
                offending_lines=[lines[item["token"]["line"] - 1]],
                is_fixable=True,
            )
            for item in self._find_edits(content)
        ]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        chars = list(content)
        for item in sorted(self._find_edits(content), key=lambda edit: edit["start"], reverse=True):
            chars[item["start"]:item["end"]] = list(item["replacement"])
        return "".join(chars)
