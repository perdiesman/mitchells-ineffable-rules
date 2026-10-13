"""Read and safely update staged Git documents."""

from __future__ import annotations

import difflib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


class GitStagedError(RuntimeError):
    pass


@dataclass(frozen=True)
class StagedDocument:
    path: str
    mode: str
    content: str
    changed_lines: frozenset[int]


def _run(
    args: list[str],
    *,
    cwd: Path,
    input_data: bytes | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(args, cwd=cwd, input=input_data, capture_output=True, check=check)


def repository_root(cwd: str | os.PathLike[str] = ".") -> Path:
    result = _run(["git", "rev-parse", "--show-toplevel"], cwd=Path(cwd).resolve())
    return Path(result.stdout.decode().strip())


def _changed_lines(root: Path, path: str) -> frozenset[int]:
    result = _run(
        ["git", "diff", "--cached", "--unified=0", "--no-color", "--", path],
        cwd=root,
    )
    lines: set[int] = set()
    for raw_line in result.stdout.decode("utf-8", "replace").splitlines():
        match = _HUNK.match(raw_line)
        if not match:
            continue
        start = int(match.group(1))
        count = int(match.group(2) or "1")
        lines.update(range(start, start + count)) if count else lines.add(max(1, start))
    return frozenset(lines)


def read_staged_documents(root: Path, supported_extensions: Iterable[str]) -> list[StagedDocument]:
    extensions = {extension.lower() for extension in supported_extensions}
    names = _run(
        ["git", "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"],
        cwd=root,
    ).stdout.split(b"\0")
    documents: list[StagedDocument] = []
    for raw_name in names:
        if not raw_name:
            continue
        path = raw_name.decode("utf-8", "surrogateescape")
        if Path(path).suffix.lower() not in extensions:
            continue
        blob = _run(["git", "show", f":{path}"], cwd=root).stdout
        try:
            content = blob.decode("utf-8")
        except UnicodeDecodeError:
            continue
        entry = _run(["git", "ls-files", "-s", "--", path], cwd=root).stdout.decode().strip()
        if entry:
            documents.append(
                StagedDocument(path, entry.split(maxsplit=1)[0], content, _changed_lines(root, path))
            )
    return documents


def _patch(path: str, before: str, after: str) -> bytes:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            n=3,
        )
    ).encode("utf-8")


def update_staged_documents(root: Path, changes: list[tuple[StagedDocument, str]]) -> list[str]:
    """Update the index and merge fixes into cleanly applicable working trees."""
    prepared: list[tuple[StagedDocument, str, str, bytes]] = []
    for document, fixed in changes:
        if fixed == document.content:
            continue
        object_id = _run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=root,
            input_data=fixed.encode("utf-8"),
        ).stdout.decode().strip()
        prepared.append((document, fixed, object_id, _patch(document.path, document.content, fixed)))

    if not prepared:
        return []
    index_info = b"".join(
        f"{document.mode} {object_id}\t{document.path}\0".encode("utf-8", "surrogateescape")
        for document, _, object_id, _ in prepared
    )
    _run(["git", "update-index", "-z", "--index-info"], cwd=root, input_data=index_info)

    warnings: list[str] = []
    for document, fixed, _, patch in prepared:
        working_path = root / document.path
        try:
            working_content = working_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            warnings.append(f"{document.path}: staged content fixed; working tree could not be synchronized")
            continue
        if working_content == document.content:
            working_path.write_text(fixed, encoding="utf-8", newline="")
            continue
        if working_content.startswith(document.content):
            working_path.write_text(
                fixed + working_content[len(document.content) :],
                encoding="utf-8",
                newline="",
            )
            continue
        check = _run(
            ["git", "apply", "--check", "--whitespace=nowarn", "-"],
            cwd=root,
            input_data=patch,
            check=False,
        )
        if check.returncode == 0:
            _run(["git", "apply", "--whitespace=nowarn", "-"], cwd=root, input_data=patch)
        else:
            warnings.append(
                f"{document.path}: staged content fixed; overlapping unstaged edits were preserved unchanged"
            )
    return warnings
