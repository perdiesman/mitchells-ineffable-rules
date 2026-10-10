from typing import Any, Dict, List

from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.indent import IndentRule
from mir.rules.sql.sql_utils import get_token_depths, tokenize_sql


class SetMultiRule(BaseRule):
    commit_profile = True
    embedded_safe = True
    rule_id = "IR-set-multi"
    description = "Put each assignment in a multiline SET clause on its own indented line."
    category = "data-modification"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {"indent_size": 4}
    config_options = {
        "indent_size": {
            "default": 4,
            "description": "Spaces used to indent SET assignments.",
            "fallback": "IR-indent:indent_size",
        }
    }

    examples = [{
        "violating": "SET first_value = excluded.first_value,\n    second_value = excluded.second_value",
        "correct": "SET\n    first_value = excluded.first_value,\n    second_value = excluded.second_value",
    }]
    additional_validations = ["SET work_mem TO '128MB';"]

    def _find_violations(
        self, content: str, rule_config: Dict[str, Any]
    ) -> List[dict]:
        tokens = tokenize_sql(content)
        depths = get_token_depths(tokens)
        indent_size = self.get_config_value(
            rule_config,
            "indent_size",
            4,
            fallbacks=[(IndentRule, "indent_size")],
        )
        violations = []

        for set_index, token in enumerate(tokens):
            if token["type"] != "KEYWORD" or token["value"].upper() != "SET":
                continue
            line_start = content.rfind("\n", 0, token["start"]) + 1
            prefix = content[line_start:token["start"]]
            if prefix.strip():
                continue
            depth = depths[set_index]
            clause_end = len(tokens)
            for index in range(set_index + 1, len(tokens)):
                candidate = tokens[index]
                if depths[index] != depth:
                    continue
                if candidate["type"] == "SEMI":
                    clause_end = index
                    break
                if (
                    candidate["type"] == "KEYWORD"
                    and candidate["value"].upper()
                    in {"FROM", "WHERE", "RETURNING"}
                ):
                    clause_end = index
                    break

            comma_indices = [
                index
                for index in range(set_index + 1, clause_end)
                if depths[index] == depth and tokens[index]["type"] == "COMMA"
            ]
            if not comma_indices:
                continue

            fields = []
            field_start = token["end"]
            for comma_index in comma_indices:
                field = content[field_start:tokens[comma_index]["start"]].strip()
                if field:
                    fields.append(field + ",")
                field_start = tokens[comma_index]["end"]
            last_active = next(
                (
                    tokens[index]
                    for index in range(clause_end - 1, set_index, -1)
                    if tokens[index]["type"] not in ("WHITESPACE", "COMMENT")
                ),
                None,
            )
            if last_active is None:
                continue
            final_field = content[field_start:last_active["end"]].strip()
            if not final_field:
                continue
            fields.append(final_field)

            indent = prefix[: len(prefix) - len(prefix.lstrip(" \t"))]
            expected = "SET\n" + "\n".join(
                indent + " " * indent_size + field for field in fields
            )
            original = content[token["start"]:last_active["end"]]
            if original != expected:
                violations.append({
                    "token": token,
                    "start": token["start"],
                    "end": last_active["end"],
                    "replacement": expected,
                })
        return violations

    def check(
        self, content: str, file_path: str, rule_config: Dict[str, Any]
    ) -> List[Violation]:
        lines = content.splitlines()
        return [
            Violation(
                rule_id=self.rule_id,
                line_number=item["token"]["line"],
                message="Each assignment in a multiline SET clause should use its own line.",
                offending_lines=[lines[item["token"]["line"] - 1]],
                is_fixable=True,
            )
            for item in self._find_violations(content, rule_config)
        ]

    def fix(
        self, content: str, file_path: str, rule_config: Dict[str, Any]
    ) -> str:
        edits = self._find_violations(content, rule_config)
        chars = list(content)
        for item in sorted(edits, key=lambda item: item["start"], reverse=True):
            chars[item["start"]:item["end"]] = list(item["replacement"])
        return "".join(chars)
