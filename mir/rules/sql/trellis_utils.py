"""Parsing helpers for pyGARDEN Trellis comment-directed SQL templates."""

from __future__ import annotations

import re
import shlex
from typing import NamedTuple, Optional


_DIRECTIVE = re.compile(r"^(?P<indent>[ \t]*)--\s*trellis\s*:\s*(?P<body>.*?)\s*$", re.IGNORECASE)


class TrellisDirective(NamedTuple):
    line: int
    indent: str
    keyword: str
    argument: str
    original: str

    @property
    def canonical(self) -> str:
        suffix = f" {self.argument}" if self.argument else ""
        return f"{self.indent}-- trellis: {self.keyword}{suffix}"


class TrellisIssue(NamedTuple):
    line: int
    message: str


def parse_directive(line: str, line_number: int) -> Optional[TrellisDirective]:
    match = _DIRECTIVE.match(line.rstrip("\r\n"))
    if not match:
        return None
    body = match.group("body").strip()
    keyword, _, argument = body.partition(" ")
    return TrellisDirective(
        line_number,
        match.group("indent"),
        keyword.lower(),
        argument.strip(),
        line.rstrip("\r\n"),
    )


def has_trellis_directives(content: str) -> bool:
    return any(parse_directive(line, number) for number, line in enumerate(content.splitlines(), 1))


def has_trellis_syntax(content: str) -> bool:
    """Recognize directive templates and external SQL with named binds."""
    if has_trellis_directives(content):
        return True
    # Import lazily to avoid making the tokenizer depend on Trellis parsing.
    from mir.rules.sql.sql_utils import tokenize_sql

    return any(
        token["type"] == "PARAM" and token["value"].startswith(":")
        for token in tokenize_sql(content)
    )


def analyze_trellis(content: str) -> tuple[list[TrellisDirective], list[TrellisIssue], list[tuple[int, int]]]:
    directives: list[TrellisDirective] = []
    issues: list[TrellisIssue] = []
    ranges: list[tuple[int, int]] = []
    stack: list[dict] = []
    closers = {"endif": "if", "endchoose": "choose", "endfor": "for"}

    for line_number, line in enumerate(content.splitlines(), 1):
        directive = parse_directive(line, line_number)
        if directive is None:
            continue
        directives.append(directive)
        keyword = directive.keyword
        argument = directive.argument

        if keyword in {"if", "choose"}:
            if not argument:
                issues.append(TrellisIssue(line_number, f"{keyword} requires an expression."))
            stack.append({"kind": keyword, "line": line_number, "terminal": False})
        elif keyword == "for":
            try:
                parts = shlex.split(f"for {argument}")
            except ValueError as error:
                issues.append(TrellisIssue(line_number, f"Invalid for directive: {error}."))
                parts = []
            if len(parts) < 4 or parts[2].lower() != "in":
                issues.append(TrellisIssue(line_number, "Expected 'for item in collection'."))
            elif any("=" not in part for part in parts[4:]):
                issues.append(TrellisIssue(line_number, "For options must use name=value syntax."))
            stack.append({"kind": "for", "line": line_number, "terminal": False})
        elif keyword in {"elif", "else"}:
            if not stack or stack[-1]["kind"] != "if":
                issues.append(TrellisIssue(line_number, f"{keyword} must be inside an if block."))
            elif stack[-1]["terminal"]:
                issues.append(TrellisIssue(line_number, f"{keyword} cannot follow else."))
            elif keyword == "elif" and not argument:
                issues.append(TrellisIssue(line_number, "elif requires an expression."))
            elif keyword == "else":
                if argument:
                    issues.append(TrellisIssue(line_number, "else does not accept an expression."))
                stack[-1]["terminal"] = True
        elif keyword in {"when", "otherwise"}:
            if not stack or stack[-1]["kind"] != "choose":
                issues.append(TrellisIssue(line_number, f"{keyword} must be inside a choose block."))
            elif stack[-1]["terminal"]:
                issues.append(TrellisIssue(line_number, f"{keyword} cannot follow otherwise."))
            elif keyword == "when" and not argument:
                issues.append(TrellisIssue(line_number, "when requires an expression."))
            elif keyword == "otherwise":
                if argument:
                    issues.append(TrellisIssue(line_number, "otherwise does not accept an expression."))
                stack[-1]["terminal"] = True
        elif keyword in closers:
            expected = closers[keyword]
            if argument:
                issues.append(TrellisIssue(line_number, f"{keyword} does not accept an expression."))
            if not stack or stack[-1]["kind"] != expected:
                issues.append(TrellisIssue(line_number, f"{keyword} has no matching {expected}."))
            else:
                opener = stack.pop()
                ranges.append((opener["line"], line_number))
        else:
            issues.append(TrellisIssue(line_number, f"Unknown Trellis directive '{keyword or '<empty>'}'."))

    for opener in stack:
        issues.append(TrellisIssue(opener["line"], f"Unclosed {opener['kind']} directive."))
    return directives, issues, ranges
