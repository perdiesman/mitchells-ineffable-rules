"""Git-free batch exchange used by the containerized commit hook."""

from __future__ import annotations

import base64
import difflib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from mir.engine.disabler import get_file_language
from mir.engine.git_staged import changed_lines_from_diff
from mir.engine.selection import expand_selection

if TYPE_CHECKING:
    from mir.engine.config import Config


SCHEMA_VERSION = 1
_DOCUMENT_ID = re.compile(r"^[0-9]{6}$")
_REGULAR_MODES = {"100644", "100755"}


class BatchManifestError(ValueError):
    pass


def _exchange_path(root: Path, value: object, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise BatchManifestError(f"{field} must be a non-empty path")
    candidate = (root / value).resolve()
    if candidate != root and root not in candidate.parents:
        raise BatchManifestError(f"{field} escapes the exchange directory")
    return candidate


def _logical_path(encoded: object) -> str:
    if not isinstance(encoded, str) or not encoded:
        raise BatchManifestError("path_base64 must be a non-empty string")
    try:
        path = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as error:
        raise BatchManifestError("path_base64 is not valid UTF-8 base64") from error
    pure_path = PurePosixPath(path)
    if not path or pure_path.is_absolute() or ".." in pure_path.parts or "\0" in path:
        raise BatchManifestError("document path must be repository-relative")
    return path


def _load_records(manifest: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for line_number, raw_line in enumerate(
        manifest.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line.strip():
            continue
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError as error:
            raise BatchManifestError(
                f"invalid JSON on manifest line {line_number}: {error.msg}"
            ) from error
        if (
            not isinstance(record, dict)
            or record.get("schema_version") != SCHEMA_VERSION
        ):
            raise BatchManifestError(
                f"manifest line {line_number} must use schema_version {SCHEMA_VERSION}"
            )
        document_id = record.get("id")
        if not isinstance(document_id, str) or not _DOCUMENT_ID.fullmatch(document_id):
            raise BatchManifestError(
                f"manifest line {line_number} has an invalid document id"
            )
        if document_id in seen_ids:
            raise BatchManifestError(f"duplicate document id {document_id}")
        seen_ids.add(document_id)
        records.append(record)
    return records


def _patch(path: str, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            n=3,
        )
    )


def run_batch(config: Config) -> int:
    """Process staged snapshots without consulting a Git repository."""
    from mir.engine.runner import _print_result, process_document

    assert config.batch_manifest is not None
    assert config.batch_output is not None
    manifest = Path(config.batch_manifest).resolve()
    exchange_root = manifest.parent.resolve()
    output_root = Path(config.batch_output).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    result_records: list[dict[str, Any]] = []
    total_errors = 0

    try:
        records = _load_records(manifest)
    except (OSError, BatchManifestError) as error:
        print(f"Invalid batch manifest: {error}", file=sys.stderr)
        return 2

    for record in records:
        document_id = str(record["id"])
        output_dir = output_root / document_id
        output_dir.mkdir(parents=True, exist_ok=True)
        result_record: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "id": document_id,
        }
        try:
            path = _logical_path(record.get("path_base64"))
            mode = record.get("mode")
            if mode not in _REGULAR_MODES:
                result_record.update(status="skipped", reason="non-regular-file")
                result_records.append(result_record)
                continue
            content_path = _exchange_path(
                exchange_root, record.get("content_file"), "content_file"
            )
            diff_path = _exchange_path(
                exchange_root, record.get("diff_file"), "diff_file"
            )
            content = content_path.read_text(encoding="utf-8")
            changed_lines = changed_lines_from_diff(
                diff_path.read_text(encoding="utf-8", errors="replace")
            )
        except UnicodeDecodeError:
            result_record.update(status="skipped", reason="non-utf8-content")
            result_records.append(result_record)
            continue
        except (OSError, BatchManifestError) as error:
            print(f"Batch document {document_id}: {error}", file=sys.stderr)
            result_record.update(status="error", reason=str(error), errors=1)
            result_records.append(result_record)
            total_errors += 1
            continue

        language = get_file_language(path)
        if language == "unknown":
            result_record.update(status="skipped", reason="unsupported-language")
            result_records.append(result_record)
            continue

        selection = expand_selection(content, language, changed_lines)
        result = process_document(config, content, path, language, selection)
        _print_result(config, result)
        total_errors += result.errors
        changed = result.content != content
        result_record.update(
            path=path,
            status="changed" if changed else "unchanged",
            errors=result.errors,
            warnings=result.warnings,
            rules_fixed=sorted(result.rules_fixed),
            diagnostics=list(result.diagnostics),
        )
        if config.fix and changed:
            (output_dir / "content").write_text(
                result.content, encoding="utf-8", newline=""
            )
            (output_dir / "working-tree.patch").write_text(
                _patch(path, content, result.content),
                encoding="utf-8",
                newline="",
            )
            if not config.quiet:
                print(
                    f"Fixed staged issues in {path} "
                    f"({', '.join(sorted(result.rules_fixed))})"
                )
        result_records.append(result_record)

    result_manifest = output_root / "result.jsonl"
    result_manifest.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in result_records),
        encoding="utf-8",
    )
    return 1 if total_errors else 0
