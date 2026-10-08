"""Immutable changed-line selection and construct expansion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Iterable


@dataclass(frozen=True)
class LineSelection:
    """Changed and authorized one-based lines for a single document."""

    changed: FrozenSet[int] = frozenset()
    allowed: FrozenSet[int] = frozenset()

    @classmethod
    def all(cls) -> "LineSelection":
        return cls()

    @property
    def restricted(self) -> bool:
        return bool(self.allowed)

    def contains(self, line_number: int) -> bool:
        return not self.allowed or line_number in self.allowed


def _line_at(content: str, offset: int) -> int:
    return content.count("\n", 0, max(0, offset)) + 1


def _expand_sql(content: str, changed: set[int]) -> set[int]:
    from mir.rules.sql.sql_utils import tokenize_sql

    tokens = tokenize_sql(content)
    ranges: list[tuple[int, int]] = []
    statement_start: int | None = None
    for token in tokens:
        if statement_start is None and token["type"] not in {"WHITESPACE", "COMMENT"}:
            statement_start = _line_at(content, token["start"])
        if token["type"] == "SEMI":
            end = _line_at(content, token["end"])
            ranges.append((statement_start or end, end))
            statement_start = None
    final_line = content.count("\n") + 1
    if statement_start is not None and statement_start <= final_line:
        ranges.append((statement_start, final_line))

    expanded = set(changed)
    for start, end in ranges:
        if changed.intersection(range(start, end + 1)):
            expanded.update(range(start, end + 1))

    for token in tokens:
        value = token["value"]
        if token["type"] == "STRING" and value.startswith("$"):
            start = _line_at(content, token["start"])
            end = _line_at(content, token["end"])
            if changed.intersection(range(start, end + 1)):
                expanded.update(range(start, end + 1))
    return expanded


def _expand_xml(content: str, changed: set[int]) -> set[int]:
    from mir.rules.xml.xml_mybatis_sql import get_all_elements_recursively, parse_xml_elements
    from mir.rules.xml.xml_utils import tokenize_xml

    tokens = tokenize_xml(content)
    elements = get_all_elements_recursively(parse_xml_elements(tokens))
    expanded = set(changed)
    for element in elements:
        if element["tag"] not in {"select", "insert", "update", "delete", "sql"}:
            continue
        start = _line_at(content, element["start_offset"])
        end = _line_at(content, element["end_offset"])
        if changed.intersection(range(start, end + 1)):
            expanded.update(range(start, end + 1))
    return expanded


def expand_selection(content: str, language: str, lines: Iterable[int]) -> LineSelection:
    changed = {line for line in lines if line > 0}
    if not changed:
        return LineSelection.all()
    try:
        allowed = _expand_xml(content, changed) if language == "xml" else _expand_sql(content, changed)
    except Exception:
        allowed = changed
    return LineSelection(frozenset(changed), frozenset(allowed))
