from typing import Any, Dict, List

from mir.engine.rule_interface import BaseRule, Violation
from mir.rules.sql.sql_utils import tokenize_sql


class TrailingWhitespaceRule(BaseRule):
    commit_profile = True
    trellis_safe = True
    rule_id = "IR-trailing-whitespace"
    description = "Remove spaces and tabs at the ends of SQL lines without changing quoted literal or identifier contents."
    category = "general"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {}
    config_options = {}

    examples = [
        {
            "violating": "SELECT item_id FROM sample_item;   \n",
            "correct": "SELECT item_id FROM sample_item;\n",
        }
    ]
    additional_validations = ["SELECT item_id FROM sample_item;\n"]

    @staticmethod
    def _line_numbers(content: str) -> List[int]:
        quoted = [
            token
            for token in tokenize_sql(content)
            if token["type"] == "STRING"
            or token["type"] == "IDENTIFIER"
            and token["value"].startswith('"')
        ]
        result = []
        offset = 0
        index = 0
        for number, line in enumerate(content.splitlines(keepends=True), 1):
            body = line.rstrip("\r\n")
            trailing = offset + len(body.rstrip(" \t"))
            while index < len(quoted) and quoted[index]["end"] <= trailing:
                index += 1
            if body.endswith((" ", "\t")) and not (
                index < len(quoted)
                and quoted[index]["start"] <= trailing < quoted[index]["end"]
            ):
                result.append(number)
            offset += len(line)
        return result

    def check(
        self, content: str, file_path: str, rule_config: Dict[str, Any]
    ) -> List[Violation]:
        lines = content.splitlines()
        return [
            Violation(
                rule_id=self.rule_id,
                line_number=line_number,
                message="SQL lines must not end with spaces or tabs.",
                offending_lines=[lines[line_number - 1]],
                is_fixable=True,
            )
            for line_number in self._line_numbers(content)
        ]

    def fix(
        self, content: str, file_path: str, rule_config: Dict[str, Any]
    ) -> str:
        selected = set(self._line_numbers(content))
        if not selected:
            return content
        lines = content.splitlines(keepends=True)
        fixed = []
        for number, line in enumerate(lines, 1):
            ending = ""
            body = line
            if body.endswith("\r\n"):
                body, ending = body[:-2], "\r\n"
            elif body.endswith("\n"):
                body, ending = body[:-1], "\n"
            elif body.endswith("\r"):
                body, ending = body[:-1], "\r"
            fixed.append((body.rstrip(" \t") if number in selected else body) + ending)
        return "".join(fixed)
