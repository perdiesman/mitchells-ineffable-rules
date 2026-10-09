from typing import Any, Dict, List

from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import find_matching_paren, tokenize_sql


class DistinctRowLayoutRule(BaseRule):
    commit_profile = True
    embedded_safe = True
    rule_id = "IR-distinct-row-layout"
    description = (
        "A multi-column row used as the argument to multiline DISTINCT should "
        "put each field on its own indented line."
    )
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {}
    config_options = {}

    examples = [
        {
            "violating": "count(\n    DISTINCT (state_id, utility_id, sub_utility_id)\n)",
            "correct": (
                "count(\n"
                "    DISTINCT (\n"
                "        state_id,\n"
                "        utility_id,\n"
                "        sub_utility_id\n"
                "    )\n"
                ")"
            ),
        }
    ]
    additional_validations = [
        "count(DISTINCT (state_id, utility_id))",
        "count(\n    DISTINCT utility_id\n)",
    ]

    def _find_edits(self, content: str) -> List[dict]:
        tokens = tokenize_sql(content)
        lines = content.splitlines()
        edits = []
        for index, token in enumerate(tokens):
            if token["type"] != "KEYWORD" or token["value"].upper() != "DISTINCT":
                continue
            outer_open = next(
                (
                    candidate
                    for candidate in range(index - 1, -1, -1)
                    if tokens[candidate]["type"] not in ("WHITESPACE", "COMMENT")
                ),
                None,
            )
            if outer_open is None or tokens[outer_open]["value"] != "(":
                continue
            outer_close = find_matching_paren(tokens, outer_open)
            if outer_close is None or tokens[outer_close]["line"] == tokens[outer_open]["line"]:
                continue
            row_open = next(
                (
                    candidate
                    for candidate in range(index + 1, outer_close)
                    if tokens[candidate]["type"] not in ("WHITESPACE", "COMMENT")
                ),
                None,
            )
            if row_open is None or tokens[row_open]["value"] != "(":
                continue
            row_close = find_matching_paren(tokens, row_open)
            if row_close is None or tokens[row_close]["line"] != tokens[row_open]["line"]:
                continue

            depth = 0
            commas = []
            for candidate in range(row_open + 1, row_close):
                item = tokens[candidate]
                if item["type"] == "PAREN":
                    depth += 1 if item["value"] == "(" else -1
                elif item["type"] == "COMMA" and depth == 0:
                    commas.append(candidate)
            if not commas:
                continue

            row_line = lines[tokens[row_open]["line"] - 1]
            row_indent = row_line[: len(row_line) - len(row_line.lstrip(" \t"))]
            content_indent = row_indent + "    "
            boundaries = [(row_open, False), *[(comma, False) for comma in commas], (row_close, True)]
            for boundary, before in boundaries:
                whitespace_index = boundary - 1 if before else boundary + 1
                whitespace = (
                    tokens[whitespace_index]
                    if 0 <= whitespace_index < len(tokens)
                    and tokens[whitespace_index]["type"] == "WHITESPACE"
                    else None
                )
                boundary_token = tokens[boundary]
                start = whitespace["start"] if whitespace else (
                    boundary_token["start"] if before else boundary_token["end"]
                )
                end = whitespace["end"] if whitespace else (
                    boundary_token["start"] if before else boundary_token["end"]
                )
                replacement = "\n" + (row_indent if before else content_indent)
                if content[start:end] != replacement:
                    edits.append({
                        "token": boundary_token,
                        "start": start,
                        "end": end,
                        "replacement": replacement,
                    })
        return edits

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        lines = content.splitlines()
        return [
            Violation(
                rule_id=self.rule_id,
                line_number=item["token"]["line"],
                message="DISTINCT row fields should use one line per field.",
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
