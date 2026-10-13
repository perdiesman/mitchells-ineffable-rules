from typing import Any, Dict, List

from mir.engine.rule_interface import BaseRule, Violation


class TrailingWhitespaceRule(BaseRule):
    commit_profile = True
    trellis_safe = True
    rule_id = "IR-trailing-whitespace"
    description = "Remove spaces and tabs at the ends of SQL lines."
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
        return [
            line_number
            for line_number, line in enumerate(content.splitlines(), 1)
            if line.endswith((" ", "\t"))
        ]

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
        if not self._line_numbers(content):
            return content
        lines = content.splitlines(keepends=True)
        fixed = []
        for line in lines:
            ending = ""
            body = line
            if body.endswith("\r\n"):
                body, ending = body[:-2], "\r\n"
            elif body.endswith("\n"):
                body, ending = body[:-1], "\n"
            elif body.endswith("\r"):
                body, ending = body[:-1], "\r"
            fixed.append(body.rstrip(" \t") + ending)
        return "".join(fixed)
