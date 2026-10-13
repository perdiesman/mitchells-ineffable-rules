from typing import Any, Dict, List

from mir.engine.rule_interface import BaseRule, RuleCase, Violation
from mir.rules.xml.xml_mybatis_sql import (
    get_all_elements_recursively,
    parse_xml_elements,
)
from mir.rules.xml.xml_utils import tokenize_xml


class XmlMybatisBlankLinesRule(BaseRule):
    commit_profile = True
    rule_id = "IR-xml-mybatis-blank-lines"
    description = (
        "Remove boundary blank lines from MyBatis statements and limit blank-line "
        "runs in mapper and generator XML to one."
    )
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {}
    config_options = {}
    examples = []
    additional_validations = []
    cases = [
        RuleCase(
            "statement boundary blank lines",
            '<mapper namespace="Generic">\n'
            '    <select id="items">\n'
            '\n'
            '        SELECT item_id\n'
            '\n'
            '\n'
            '        FROM sample_item\n'
            '\n'
            '    </select>\n'
            '</mapper>',
            "fixed",
            '<mapper namespace="Generic">\n'
            '    <select id="items">\n'
            '        SELECT item_id\n'
            '\n'
            '        FROM sample_item\n'
            '    </select>\n'
            '</mapper>',
        ),
        RuleCase(
            "blank line before SQL closing parenthesis",
            '<mapper namespace="Generic">\n'
            '    <select id="items">\n'
            '        SELECT *\n'
            '        FROM (\n'
            '            SELECT item_id\n'
            '            FROM sample_item\n'
            '\n'
            '        ) items\n'
            '    </select>\n'
            '</mapper>',
            "fixed",
            '<mapper namespace="Generic">\n'
            '    <select id="items">\n'
            '        SELECT *\n'
            '        FROM (\n'
            '            SELECT item_id\n'
            '            FROM sample_item\n'
            '        ) items\n'
            '    </select>\n'
            '</mapper>',
        ),
    ]

    @staticmethod
    def _removed_lines(content: str) -> set[int]:
        lowered = content.lower()
        if "<mapper" not in lowered and "<generatorconfiguration" not in lowered:
            return set()
        tokens = tokenize_xml(content)
        elements = get_all_elements_recursively(parse_xml_elements(tokens))
        lines = content.splitlines()
        targets = {"select", "insert", "update", "delete", "sql"}
        removed: set[int] = set()

        for element in elements:
            if element["tag"] not in targets:
                continue
            opening_end = tokens[element["open_end_idx"]]
            closing_end = tokens[element["end_idx"]]
            first_inner_line = opening_end["line"] + opening_end["value"].count("\n") + 1
            closing_line = closing_end["line"]

            line_number = first_inner_line
            while line_number < closing_line and not lines[line_number - 1].strip():
                removed.add(line_number)
                line_number += 1

            line_number = closing_line - 1
            while line_number >= first_inner_line and not lines[line_number - 1].strip():
                removed.add(line_number)
                line_number -= 1

            previous_blank = False
            for line_number in range(first_inner_line, closing_line):
                if line_number in removed:
                    continue
                is_blank = not lines[line_number - 1].strip()
                if is_blank and previous_blank:
                    removed.add(line_number)
                previous_blank = is_blank

            for line_number in range(first_inner_line, closing_line):
                if lines[line_number - 1].strip():
                    continue
                next_line_number = line_number + 1
                while (
                    next_line_number < closing_line
                    and not lines[next_line_number - 1].strip()
                ):
                    next_line_number += 1
                if (
                    next_line_number < closing_line
                    and lines[next_line_number - 1].lstrip().startswith(")")
                ):
                    removed.add(line_number)

        previous_blank = False
        for line_number, line in enumerate(lines, 1):
            is_blank = not line.strip()
            if is_blank and previous_blank:
                removed.add(line_number)
            previous_blank = is_blank

        return removed

    def check(
        self, content: str, file_path: str, rule_config: Dict[str, Any]
    ) -> List[Violation]:
        lines = content.splitlines()
        removed = self._removed_lines(content)
        whitespace_only = {
            line_number
            for line_number, line in enumerate(lines, 1)
            if line and not line.strip()
        }
        return [
            Violation(
                self.rule_id,
                line_number,
                (
                    "Blank lines in MyBatis files must not contain whitespace."
                    if line_number in whitespace_only and line_number not in removed
                    else "MyBatis statements must not start or end with blank lines or contain repeated blank lines."
                ),
                [lines[line_number - 1]],
                True,
            )
            for line_number in sorted(removed | whitespace_only)
        ]

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        removed = self._removed_lines(content)
        lines = content.splitlines()
        whitespace_only = any(line and not line.strip() for line in lines)
        if not removed and not whitespace_only:
            return content
        ending = "\r\n" if "\r\n" in content else "\n"
        fixed = ending.join(
            "" if line and not line.strip() else line
            for line_number, line in enumerate(lines, 1)
            if line_number not in removed
        )
        return fixed + (ending if content.endswith(("\n", "\r")) else "")
