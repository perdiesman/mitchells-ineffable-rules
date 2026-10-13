"""Shared provider process, selection, and edit helpers."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Optional

from mir.engine.provider_interface import ProviderEdit


def line_for_offset(content: str, offset: int) -> int:
    return content.count("\n", 0, max(0, offset)) + 1


def offset_for_location(content: str, row: int, column: int) -> int:
    lines = content.splitlines(keepends=True)
    if not lines:
        return 0
    row = min(max(1, row), len(lines))
    return sum(len(line) for line in lines[: row - 1]) + min(
        max(0, column - 1), len(lines[row - 1].rstrip("\r\n"))
    )


def selected_edit(content: str, edit: ProviderEdit, selected: Iterable[int], restricted: bool) -> bool:
    if not restricted:
        return True
    lines = set(range(line_for_offset(content, edit.start), line_for_offset(content, edit.end) + 1))
    return bool(lines.intersection(selected))


def apply_edits(content: str, edits: Iterable[ProviderEdit]) -> str:
    result = content
    ordered = sorted(edits, key=lambda edit: (edit.start, edit.end), reverse=True)
    previous_start = len(content) + 1
    for edit in ordered:
        if edit.end > previous_start or edit.start < 0 or edit.end < edit.start or edit.end > len(content):
            continue
        result = result[: edit.start] + edit.replacement + result[edit.end :]
        previous_start = edit.start
    return result


def find_project_executable(path: str, name: str) -> Optional[str]:
    current = Path(path).resolve().parent
    for parent in (current, *current.parents):
        candidate = parent / "node_modules" / ".bin" / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def resolve_executable(path: str, name: str, configured: object, project_local: bool = False) -> Optional[str]:
    if isinstance(configured, str) and configured not in {"", "auto"}:
        candidate = Path(configured).expanduser()
        return str(candidate) if candidate.is_file() and os.access(candidate, os.X_OK) else None
    if project_local:
        return find_project_executable(path, name)
    current = Path(path).resolve().parent
    for parent in (current, *current.parents):
        candidate = parent / ".venv" / "bin" / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return shutil.which(name)


def run_process(
    command: list[str], content: str, cwd: Optional[str] = None, timeout: float = 30.0
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        input=content,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=timeout,
        check=False,
    )


def contiguous_ranges(lines: Iterable[int]) -> list[tuple[int, int]]:
    values = sorted(set(lines))
    if not values:
        return []
    ranges: list[tuple[int, int]] = []
    start = previous = values[0]
    for value in values[1:]:
        if value != previous + 1:
            ranges.append((start, previous))
            start = value
        previous = value
    ranges.append((start, previous))
    return ranges
