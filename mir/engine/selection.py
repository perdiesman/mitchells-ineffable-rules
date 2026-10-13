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
    from mir.rules.sql.trellis_utils import analyze_trellis

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

    _, _, template_ranges = analyze_trellis(content)
    changed_or_expanded = set(expanded)
    for start, end in template_ranges:
        if changed_or_expanded.intersection(range(start, end + 1)):
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


def _expand_java(content: str, changed: set[int]) -> set[int]:
    from mir.rules.java.java_utils import named_ancestor, node_for_line, parse_java

    document = parse_java(content)
    owner_types = {
        "import_declaration",
        "method_declaration",
        "constructor_declaration",
        "compact_constructor_declaration",
        "field_declaration",
        "class_declaration",
        "interface_declaration",
        "enum_declaration",
        "record_declaration",
        "annotation_type_declaration",
        "module_declaration",
    }
    expanded = set(changed)
    imports = [child for child in document.root.named_children if child.type == "import_declaration"]
    import_lines = set()
    for node in imports:
        import_lines.update(document.lines_for(node))
    if changed.intersection(import_lines):
        for node in imports:
            expanded.update(document.lines_for(node))

    for line in changed:
        node = node_for_line(document, line)
        if node is None:
            continue
        owner = named_ancestor(node, owner_types)
        if owner is not None:
            expanded.update(document.lines_for(owner))
    return expanded


def expand_selection(content: str, language: str, lines: Iterable[int]) -> LineSelection:
    changed = {line for line in lines if line > 0}
    if not changed:
        return LineSelection.all()
    try:
        if language == "xml":
            allowed = _expand_xml(content, changed)
        elif language == "java":
            allowed = _expand_java(content, changed)
        elif language == "sql":
            allowed = _expand_sql(content, changed)
        else:
            # External providers own syntax-aware range expansion. Keep the
            # immutable Git selection narrow until the provider accepts it.
            allowed = changed
    except Exception:
        allowed = changed
    return LineSelection(frozenset(changed), frozenset(allowed))
