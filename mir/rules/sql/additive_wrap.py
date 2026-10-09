from typing import Any, Dict, List

from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import get_token_depths, source_text_length, tokenize_sql


class AdditiveWrapRule(BaseRule):
    commit_profile = True
    embedded_safe = True
    rule_id = "IR-additive-wrap"
    description = (
        "Long additive expressions should wrap before an operator, with all "
        "continuation operators aligned one indentation level in."
    )
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {"max_line_length": 120}
    config_options = {
        "max_line_length": {
            "default": 120,
            "description": "Line length threshold for wrapping additive expressions.",
        }
    }

    examples = [
        {
            "violating": (
                "                            first_measure + second_measure + "
                "third_measure + fourth_measure + fifth_measure_with_a_long_name,"
            ),
            "correct": (
                "                            first_measure + second_measure + "
                "third_measure + fourth_measure\n"
                "                                + fifth_measure_with_a_long_name,"
            ),
        }
    ]
    additional_validations = [
        "SELECT first_measure + second_measure FROM sample_measure;",
        "SELECT first_measure\n    + second_measure FROM sample_measure;",
    ]

    def _find_edits(self, content: str, rule_config: Dict[str, Any]) -> List[dict]:
        max_length = self.get_config_value(
            rule_config,
            "max_line_length",
            default_value=120,
        )
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        lines = content.splitlines(keepends=True)
        line_starts = []
        offset = 0
        for line in lines:
            line_starts.append(offset)
            offset += len(line)

        edits = []
        for line_number, raw_line in enumerate(lines, start=1):
            line = raw_line.rstrip("\r\n")
            if source_text_length(line, rule_config) <= max_length:
                continue
            line_start = line_starts[line_number - 1]
            line_end = line_start + len(line)
            candidates = []
            for index, token in enumerate(tokens):
                if token["line"] != line_number:
                    continue
                if token["type"] != "OPERATOR" or token["value"] not in {"+", "||"}:
                    continue
                previous = next(
                    (
                        tokens[prior]
                        for prior in range(index - 1, -1, -1)
                        if tokens[prior]["type"] not in {"WHITESPACE", "COMMENT"}
                    ),
                    None,
                )
                if previous is None or previous["type"] in {"OPERATOR", "COMMA"}:
                    continue
                candidates.append((index, token, depths[index]))
            if not candidates:
                continue

            shallowest = min(depth for _, _, depth in candidates)
            candidates = [item for item in candidates if item[2] == shallowest]
            indent = line[: len(line) - len(line.lstrip(" \t"))] + "    "
            segment_start = line_start
            remaining = candidates
            while source_text_length(
                indent + content[segment_start:line_end].lstrip(" \t"),
                rule_config,
            ) > max_length:
                limit = (
                    line_start + max_length
                    if segment_start == line_start
                    else segment_start + max_length - len(indent)
                )
                eligible = [item for item in remaining if item[1]["start"] <= limit]
                if not eligible:
                    break
                index, operator, _ = eligible[-1]
                whitespace = (
                    tokens[index - 1]
                    if index > 0 and tokens[index - 1]["type"] == "WHITESPACE"
                    else None
                )
                if whitespace is None or "\n" in whitespace["value"]:
                    break
                edits.append(
                    {
                        "token": operator,
                        "start": whitespace["start"],
                        "end": whitespace["end"],
                        "replacement": "\n" + indent,
                    }
                )
                segment_start = operator["start"]
                remaining = [item for item in remaining if item[1]["start"] > segment_start]
                if not remaining:
                    break
        return edits

    def check(
        self, content: str, file_path: str, rule_config: Dict[str, Any]
    ) -> List[Violation]:
        lines = content.splitlines()
        return [
            Violation(
                rule_id=self.rule_id,
                line_number=item["token"]["line"],
                message="Long additive expression should wrap before an operator.",
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
