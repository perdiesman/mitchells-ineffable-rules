"""Shared Tree-sitter parsing and edit helpers for Java rules."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import PurePath
import fnmatch
import re
from typing import Iterable, Iterator, Mapping, Optional, Sequence

from tree_sitter import Language, Node, Parser, Tree
import tree_sitter_java


JAVA_LANGUAGE = Language(tree_sitter_java.language())
JAVA_PARSER = Parser(JAVA_LANGUAGE)


@dataclass(frozen=True)
class JavaEdit:
    start: int
    end: int
    replacement: str


@dataclass(frozen=True)
class JavaDocument:
    content: str
    source: bytes
    tree: Tree
    line_starts: tuple[int, ...]
    nodes: tuple[Node, ...]
    nodes_by_type: Mapping[str, tuple[Node, ...]]

    @property
    def root(self) -> Node:
        return self.tree.root_node

    def text(self, node: Node) -> str:
        return self.source[node.start_byte : node.end_byte].decode("utf-8")

    def line(self, node: Node) -> int:
        return node.start_point.row + 1

    def lines_for(self, node: Node) -> set[int]:
        return set(range(node.start_point.row + 1, node.end_point.row + 2))


@lru_cache(maxsize=32)
def parse_java(content: str) -> JavaDocument:
    source = content.encode("utf-8")
    starts = [0]
    for match in re.finditer(b"\n", source):
        starts.append(match.end())
    tree = JAVA_PARSER.parse(source)
    all_nodes = tuple(walk(tree.root_node))
    indexed: dict[str, list[Node]] = {}
    for node in all_nodes:
        indexed.setdefault(node.type, []).append(node)
    return JavaDocument(
        content,
        source,
        tree,
        tuple(starts),
        all_nodes,
        {node_type: tuple(nodes) for node_type, nodes in indexed.items()},
    )


def clear_java_cache() -> None:
    parse_java.cache_clear()


def walk(node: Node) -> Iterator[Node]:
    """Yield a syntax tree without allocating recursive child lists."""
    cursor = node.walk()
    reached_root = False
    while not reached_root:
        yield cursor.node
        if cursor.goto_first_child():
            continue
        if cursor.goto_next_sibling():
            continue
        while True:
            if not cursor.goto_parent():
                reached_root = True
                break
            if cursor.goto_next_sibling():
                break


def nodes_of_type(document: JavaDocument, *types: str) -> Iterator[Node]:
    return (
        node
        for node_type in types
        for node in document.nodes_by_type.get(node_type, ())
    )


def error_nodes(document: JavaDocument) -> list[Node]:
    return [
        node
        for node in document.nodes
        if node.type == "ERROR" or node.is_missing
    ]


def comment_nodes(document: JavaDocument) -> list[Node]:
    return list(nodes_of_type(document, "line_comment", "block_comment"))


def named_ancestor(node: Node, types: Iterable[str]) -> Optional[Node]:
    wanted = set(types)
    current: Optional[Node] = node
    while current is not None:
        if current.type in wanted:
            return current
        current = current.parent
    return None


def node_for_line(document: JavaDocument, line: int) -> Optional[Node]:
    if line < 1:
        return None
    row = line - 1
    best: Optional[Node] = None
    for node in document.nodes:
        if node.start_point.row <= row <= node.end_point.row:
            if best is None or node.end_byte - node.start_byte < best.end_byte - best.start_byte:
                best = node
    return best


def apply_java_edits(content: str, edits: Sequence[JavaEdit]) -> str:
    if not edits:
        return content
    ordered = sorted(edits, key=lambda edit: (edit.start, edit.end))
    previous_end = -1
    for edit in ordered:
        if edit.start < previous_end or edit.start > edit.end:
            raise ValueError("Java edits overlap or have invalid bounds")
        previous_end = edit.end
    source = content.encode("utf-8")
    for edit in reversed(ordered):
        source = source[: edit.start] + edit.replacement.encode("utf-8") + source[edit.end :]
    return source.decode("utf-8")


def edit_is_authorized(node: Node, rule_config: dict) -> bool:
    allowed = set(rule_config.get("_lines", set()))
    node_lines = set(range(node.start_point.row + 1, node.end_point.row + 2))
    disabled = set(rule_config.get("_disabled_lines", set()))
    return (not allowed or node_lines.issubset(allowed)) and not node_lines.intersection(disabled)


def span_is_authorized(document: JavaDocument, start: int, end: int, rule_config: dict) -> bool:
    start_line = document.source[:start].count(b"\n") + 1
    end_line = document.source[:end].count(b"\n") + 1
    lines = set(range(start_line, end_line + 1))
    allowed = set(rule_config.get("_lines", set()))
    disabled = set(rule_config.get("_disabled_lines", set()))
    return (not allowed or lines.issubset(allowed)) and not lines.intersection(disabled)


def nontrivia_signature(content: str) -> tuple[tuple[str, str], ...]:
    document = parse_java(content)
    ignored = {"line_comment", "block_comment"}
    leaves = []
    for node in document.nodes:
        if node.child_count or node.type in ignored:
            continue
        leaves.append((node.type, document.text(node)))
    return tuple(leaves)


def comment_signature(content: str) -> tuple[str, ...]:
    document = parse_java(content)
    return tuple(document.text(node) for node in comment_nodes(document))


def protected_java_signature(content: str) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
    return nontrivia_signature(content), comment_signature(content)


def protected_java_multiset_signature(content: str) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
    tokens, comments = protected_java_signature(content)
    return tuple(sorted(tokens)), comments


DEFAULT_GENERATED_PATHS = (
    "**/target/generated-sources/**",
    "**/build/generated/**",
    "**/generated-sources/**",
    "**/generated/**",
)
DEFAULT_GENERATED_MARKERS = ("do not edit", "generated source", "generated by")


def generated_mode(file_path: str, content: str, language_config: dict) -> str:
    generated = language_config.get("generated", {})
    if not isinstance(generated, dict):
        generated = {}
    mode = str(generated.get("mode", "skip")).lower()
    patterns = tuple(generated.get("path_patterns", DEFAULT_GENERATED_PATHS))
    normalized = str(PurePath(file_path)).replace("\\", "/")
    path_match = any(fnmatch.fnmatch(normalized, pattern) for pattern in patterns)
    header = "\n".join(content.splitlines()[:20]).lower()
    markers = tuple(str(value).lower() for value in generated.get("header_markers", DEFAULT_GENERATED_MARKERS))
    marker_match = any(marker in header for marker in markers)
    annotation_names = {str(value).lower() for value in generated.get("annotations", ["Generated"])}
    annotation_match = any(
        document_name.split(".")[-1].lower() in annotation_names
        for document_name in re.findall(r"@([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)", header)
    )
    return mode if path_match or marker_match or annotation_match else "format"


def is_generated_source(file_path: str, content: str, language_config: dict) -> bool:
    return generated_mode(file_path, content, language_config) != "format"


def leading_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def line_ending(content: str) -> str:
    return "\r\n" if "\r\n" in content else "\n"
