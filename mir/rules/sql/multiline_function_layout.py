from typing import Any, Dict, List

from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import find_matching_paren, tokenize_sql
from mir.rules.sql.table_function_indent import table_function_parens


class MultilineFunctionLayoutRule(BaseRule):
    commit_profile = True
    embedded_safe = True
    embedded_dynamic_indent_safe = True
    rule_id = "IR-multiline-function-layout"
    description = (
        "Multiline function calls and single-row VALUES lists should put every "
        "direct argument on its own indented line and align the closing "
        "parenthesis with the caller."
    )
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {"indent_size": 4}
    config_options = {
        "indent_size": {
            "default": 4,
            "description": "Spaces added for function arguments.",
            "fallback": "IR-indent:indent_size",
        }
    }

    examples = [
        {
            "violating": "coalesce(item_count,\n0)",
            "correct": (
                "coalesce(\n"
                "    item_count,\n"
                "    0\n"
                ")"
            ),
        }
    ]
    additional_validations = ["sum(item_count)", "coalesce(item_count, 0)"]

    def _find_edits(self, content: str, rule_config: Dict[str, Any]) -> List[dict]:
        tokens = tokenize_sql(content)
        lines = content.splitlines()
        table_openings = table_function_parens(tokens)
        boundary_offsets = rule_config.get("mybatis_boundary_offsets", set())
        indent_size = self.get_config_value(rule_config, "indent_size", 4)
        unit = " " * indent_size
        edits = []

        def edit_whitespace(index: int, replacement: str, before: bool) -> None:
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

        for open_index, opening in enumerate(tokens):
            if (
                opening["type"] != "PAREN"
                or opening["value"] != "("
                or open_index in table_openings
            ):
                continue
            name_index = next(
                (
                    candidate
                    for candidate in range(open_index - 1, -1, -1)
                    if tokens[candidate]["type"] not in ("WHITESPACE", "COMMENT")
                ),
                None,
            )
            if name_index is None or tokens[name_index]["type"] not in (
                "IDENTIFIER",
                "KEYWORD",
            ):
                continue
            if (
                tokens[name_index]["type"] == "KEYWORD"
                and tokens[name_index]["value"].upper()
                not in {"COALESCE", "NULLIF", "VALUES"}
            ):
                continue
            close_index = find_matching_paren(tokens, open_index)
            if close_index is None or tokens[close_index]["line"] == opening["line"]:
                continue
            line = lines[opening["line"] - 1]
            base_indent = line[: len(line) - len(line.lstrip(" \t"))]
            argument_indent = base_indent + unit
            edit_whitespace(open_index, "\n" + argument_indent, before=False)
            edit_whitespace(close_index, "\n" + base_indent, before=True)

            depth = 0
            for candidate in range(open_index + 1, close_index):
                token = tokens[candidate]
                if token["type"] == "PAREN":
                    depth += 1 if token["value"] == "(" else -1
                elif token["type"] == "COMMA" and depth == 0:
                    if token["start"] in boundary_offsets:
                        continue
                    edit_whitespace(
                        candidate, "\n" + argument_indent, before=False
                    )

        return list({(item["start"], item["end"]): item for item in edits}.values())

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        lines = content.splitlines()
        return [
            Violation(
                rule_id=self.rule_id,
                line_number=item["token"]["line"],
                message="Multiline function arguments should use one aligned line per argument.",
                offending_lines=[lines[item["token"]["line"] - 1]],
                is_fixable=True,
            )
            for item in self._find_edits(content, rule_config)
        ]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        chars = list(content)
        for item in sorted(self._find_edits(content, rule_config), key=lambda edit: edit["start"], reverse=True):
            chars[item["start"]:item["end"]] = list(item["replacement"])
        return "".join(chars)
