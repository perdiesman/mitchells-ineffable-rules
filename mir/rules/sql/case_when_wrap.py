from typing import Any, Dict, List

from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import get_token_depths, source_text_length, tokenize_sql


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

    default_config = {"max_line_length": 100}
    config_options = {
        "max_line_length": {
            "default": 100,
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
                "                WHEN a_very_long_condition_name = :condition_value "
                "AND another_long_condition_name = :other_value\n"
                "                    THEN calculate_a_very_long_result_name(:result_value)\n"
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
            default_value=100,
        )
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        lines = content.splitlines()
        edits = []
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
            indent = prefix[: len(prefix) - len(prefix.lstrip(" \t"))] + "    "
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
