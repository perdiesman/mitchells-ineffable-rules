from typing import Any, Dict, List

from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import (
    find_boolean_operator_indices,
    get_token_depths,
    source_text_length,
    tokenize_sql,
)


class CaseWhenWrapRule(BaseRule):
    commit_profile = True
    embedded_safe = True
    rule_id = "IR-case-when-wrap"
    description = (
        "Keep WHEN and THEN on one line when they fit; otherwise put THEN on "
        "an indented continuation line."
    )
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {"max_line_length": 110}
    config_options = {
        "max_line_length": {
            "default": 110,
            "description": "Line length threshold for wrapping a WHEN/THEN arm.",
        }
    }

    examples = [
        {
            "violating": (
                "CASE\n"
                "                WHEN a_very_long_condition_name = :condition_value "
                "AND another_long_condition_name = :other_value THEN "
                "calculate_a_very_long_result_name(:result_value)\n"
                "    ELSE 0\n"
                "END"
            ),
            "correct": (
                "CASE\n"
                "    WHEN a_very_long_condition_name = :condition_value\n"
                "        AND another_long_condition_name = :other_value\n"
                "        THEN calculate_a_very_long_result_name(:result_value)\n"
                "    ELSE 0\n"
                "END"
            ),
        }
    ]
    additional_validations = [
        "CASE WHEN enabled THEN value ELSE 0 END",
        "CASE\n    WHEN enabled\n        THEN value\n    ELSE 0\nEND",
    ]

    def _find_edits(self, content: str, rule_config: Dict[str, Any]) -> List[dict]:
        max_length = self.get_config_value(
            rule_config,
            "max_line_length",
            default_value=110,
        )
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        lines = content.splitlines()
        edits = []
        case_inner_indents: Dict[int, str] = {}

        case_stack = []
        case_blocks = []
        for token_index, current in enumerate(tokens):
            if current["type"] != "KEYWORD":
                continue
            value = current["value"].upper()
            if value == "CASE":
                case_stack.append(token_index)
            elif value == "END" and case_stack:
                case_blocks.append((case_stack.pop(), token_index))

        for case_index, end_index in case_blocks:
            case_token = tokens[case_index]
            end_token = tokens[end_index]
            if case_token["line"] == end_token["line"]:
                continue
            case_line = lines[case_token["line"] - 1]
            case_indent = case_line[: len(case_line) - len(case_line.lstrip(" \t"))]
            inner_indent = case_indent + "    "
            nested_depth = 0
            for token_index in range(case_index + 1, end_index + 1):
                current = tokens[token_index]
                if current["type"] != "KEYWORD":
                    continue
                value = current["value"].upper()
                if value == "CASE":
                    nested_depth += 1
                    continue
                if value == "END" and nested_depth:
                    nested_depth -= 1
                    continue
                if nested_depth or value not in {"WHEN", "ELSE", "END"}:
                    continue
                if value == "WHEN":
                    case_inner_indents[token_index] = inner_indent
                whitespace = (
                    tokens[token_index - 1]
                    if token_index > 0
                    and tokens[token_index - 1]["type"] == "WHITESPACE"
                    else None
                )
                replacement = "\n" + (
                    case_indent if value == "END" else inner_indent
                )
                start = whitespace["start"] if whitespace else current["start"]
                end = whitespace["end"] if whitespace else current["start"]
                if content[start:end] != replacement:
                    edits.append(
                        {
                            "token": current,
                            "start": start,
                            "end": end,
                            "replacement": replacement,
                        }
                    )

        for index, token in enumerate(tokens):
            if token["type"] != "KEYWORD" or token["value"].upper() != "WHEN":
                continue
            then_index = next(
                (
                    candidate
                    for candidate in range(index + 1, len(tokens))
                    if depths[candidate] == depths[index]
                    and tokens[candidate]["type"] == "KEYWORD"
                    and tokens[candidate]["value"].upper() in {"THEN", "WHEN", "ELSE", "END"}
                ),
                None,
            )
            if then_index is None or tokens[then_index]["value"].upper() != "THEN":
                continue
            then_token = tokens[then_index]
            if token["line"] != then_token["line"]:
                continue
            line = lines[token["line"] - 1]
            if source_text_length(line, rule_config) <= max_length:
                continue
            whitespace = (
                tokens[then_index - 1]
                if then_index > 0 and tokens[then_index - 1]["type"] == "WHITESPACE"
                else None
            )
            if whitespace is None or "\n" in whitespace["value"]:
                continue
            line_start = content.rfind("\n", 0, token["start"]) + 1
            prefix = content[line_start : token["start"]]
            when_indent = case_inner_indents.get(
                index,
                prefix[: len(prefix) - len(prefix.lstrip(" \t"))],
            )
            indent = when_indent + "    "
            condition_line = content[line_start:then_token["start"]].rstrip()
            if source_text_length(condition_line, rule_config) > max_length:
                for boolean_index in find_boolean_operator_indices(
                    tokens,
                    depths,
                    depths[index],
                    index + 1,
                    then_index,
                ):
                    boolean_token = tokens[boolean_index]
                    boolean_whitespace = (
                        tokens[boolean_index - 1]
                        if boolean_index > 0
                        and tokens[boolean_index - 1]["type"] == "WHITESPACE"
                        else None
                    )
                    if (
                        boolean_whitespace is not None
                        and "\n" not in boolean_whitespace["value"]
                    ):
                        edits.append(
                            {
                                "token": boolean_token,
                                "start": boolean_whitespace["start"],
                                "end": boolean_whitespace["end"],
                                "replacement": "\n" + indent,
                            }
                        )
            edits.append(
                {
                    "token": then_token,
                    "start": whitespace["start"],
                    "end": whitespace["end"],
                    "replacement": "\n" + indent,
                }
            )
        return edits

    def check(
        self, content: str, file_path: str, rule_config: Dict[str, Any]
    ) -> List[Violation]:
        lines = content.splitlines()
        return [
            Violation(
                rule_id=self.rule_id,
                line_number=item["token"]["line"],
                message="THEN in a long CASE arm should start on an indented line.",
                offending_lines=[lines[item["token"]["line"] - 1]],
                is_fixable=True,
            )
            for item in self._find_edits(content, rule_config)
        ]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        edits = self._find_edits(content, rule_config)
        if not edits:
            return content
        chars = list(content)
        for item in sorted(edits, key=lambda edit: edit["start"], reverse=True):
            chars[item["start"] : item["end"]] = list(item["replacement"])
        return "".join(chars)
