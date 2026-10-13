import re
from typing import Any, Dict, List

from mir.engine.rule_interface import BaseRule, Violation


MYBATIS_SQL_TAGS = {"select", "insert", "update", "delete", "sql"}


class XmlSqlEntitiesRule(BaseRule):
    commit_profile = True
    rule_id = "IR-xml-sql-entities"
    description = (
        "Raw greater-than characters in MyBatis SQL text must be encoded as "
        "&gt;; XML tags, attributes, comments, and CDATA remain unchanged."
    )
    category = "queries"
    is_fixable = "yes"
    enabled_by_default = True

    default_config = {}
    config_options = {}

    examples = [
        {
            "violating": (
                '<select id="items">SELECT payload -> \'name\' '
                "FROM sample_item WHERE item_count > 0</select>"
            ),
            "correct": (
                '<select id="items">SELECT payload -&gt; \'name\' '
                "FROM sample_item WHERE item_count &gt; 0</select>"
            ),
        }
    ]
    additional_validations = [
        '<select id="items">SELECT payload -&gt;&gt; \'name\' FROM sample_item</select>',
        '<if test="itemCount > 0">AND item_count &gt; 0</if>',
    ]

    @staticmethod
    def _markup_end(content: str, start: int) -> int:
        """Return the offset after a tag-like construct, respecting quotes."""
        quote = None
        cursor = start
        while cursor < len(content):
            character = content[cursor]
            if quote:
                if character == quote:
                    quote = None
            elif character in {'"', "'"}:
                quote = character
            elif character == ">":
                return cursor + 1
            cursor += 1
        return len(content)

    def _find_violations(self, content: str) -> List[dict]:
        violations = []
        stack: List[str] = []
        cursor = 0
        line = 1

        def advance(end: int) -> None:
            nonlocal cursor, line
            line += content.count("\n", cursor, end)
            cursor = end

        while cursor < len(content):
            if content.startswith("<!--", cursor):
                end = content.find("-->", cursor + 4)
                advance(len(content) if end == -1 else end + 3)
                continue
            if content.startswith("<![CDATA[", cursor):
                end = content.find("]]>", cursor + 9)
                advance(len(content) if end == -1 else end + 3)
                continue
            if content.startswith("<?", cursor):
                end = content.find("?>", cursor + 2)
                advance(len(content) if end == -1 else end + 2)
                continue
            if content[cursor] == "<":
                closing = re.match(r"</([A-Za-z_:][\w:.-]*)", content[cursor:])
                opening = re.match(r"<([A-Za-z_:][\w:.-]*)", content[cursor:])
                end = self._markup_end(content, cursor + 1)
                if closing:
                    name = closing.group(1).lower()
                    if name in stack:
                        reverse_index = stack[::-1].index(name)
                        del stack[len(stack) - reverse_index - 1:]
                elif opening:
                    name = opening.group(1).lower()
                    if not content[cursor:end].rstrip().endswith("/>"):
                        stack.append(name)
                advance(end)
                continue

            next_markup = content.find("<", cursor)
            text_end = len(content) if next_markup == -1 else next_markup
            if any(name in MYBATIS_SQL_TAGS for name in stack):
                segment = content[cursor:text_end]
                segment_line = line
                for match in re.finditer(">", segment):
                    offset = cursor + match.start()
                    violations.append({
                        "line": segment_line + segment.count("\n", 0, match.start()),
                        "start_offset": offset,
                        "end_offset": offset + 1,
                        "replacement": "&gt;",
                        "message": (
                            "Greater-than characters in MyBatis SQL text "
                            "should be encoded as &gt;."
                        ),
                    })
            advance(text_end)

        return violations

    def check(
        self, content: str, file_path: str, rule_config: Dict[str, Any]
    ) -> List[Violation]:
        lines = content.splitlines()
        return [
            Violation(
                rule_id=self.rule_id,
                line_number=item["line"],
                message=item["message"],
                offending_lines=[
                    lines[item["line"] - 1]
                    if 0 < item["line"] <= len(lines)
                    else ""
                ],
                is_fixable=True,
            )
            for item in self._find_violations(content)
        ]

    def fix(
        self, content: str, file_path: str, rule_config: Dict[str, Any]
    ) -> str:
        chars = list(content)
        for item in reversed(self._find_violations(content)):
            chars[item["start_offset"]:item["end_offset"]] = item["replacement"]
        return "".join(chars)
