#!/usr/bin/env python3
"""Record or verify ignored compatibility outputs with SHA-256 manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


SCHEMA_VERSION = 1


def git_value(repository: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def git_branch(repository: Path) -> str:
    branch = git_value(repository, "branch", "--show-current")
    if branch:
        return branch
    branch = git_value(repository, "name-rev", "--name-only", "--exclude=tags/*", "HEAD")
    for prefix in ("remotes/origin/", "origin/"):
        if branch.startswith(prefix):
            return branch[len(prefix):]
    return branch


def hash_scope(repository: Path, patterns: list[str]) -> dict[str, str]:
    paths: set[Path] = set()
    for pattern in patterns:
        paths.update(path for path in repository.glob(pattern) if path.is_file())
    return {
        path.relative_to(repository).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths)
    }


def aggregate_hash(files: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for path, file_hash in sorted(files.items()):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(file_hash))
    return digest.hexdigest()


def verify_snapshot(repository: Path, snapshot: dict) -> list[str]:
    expected = snapshot["files"]
    actual = hash_scope(repository, snapshot["include"])
    issues = []
    for path in sorted(expected.keys() - actual.keys()):
        issues.append(f"missing: {path}")
    for path in sorted(actual.keys() - expected.keys()):
        issues.append(f"unexpected: {path}")
    for path in sorted(expected.keys() & actual.keys()):
        if expected[path] != actual[path]:
            issues.append(f"changed: {path}")
    if aggregate_hash(actual) != snapshot["aggregate_sha256"] and not issues:
        issues.append("aggregate hash does not match")
    return issues


def load_report(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "repositories": {}}
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Unsupported compatibility report schema: {report.get('schema_version')}")
    return report


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "verify"))
    parser.add_argument("repository", help="Directory name under the compatibility root")
    parser.add_argument(
        "--root",
        type=Path,
        default=project_root / "local" / "compat",
        help="Root containing ignored compatibility repositories",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=project_root / "local" / "compat" / "report.json",
        help="Generated compatibility report path",
    )
    parser.add_argument(
        "--include",
        action="append",
        help="Repository-relative glob to record; repeat for multiple scopes",
    )
    args = parser.parse_args()

    repository = (args.root / args.repository).resolve()
    if not (repository / ".git").exists():
        parser.error(f"Compatibility repository does not exist: {repository}")

    report = load_report(args.report)
    snapshots = report.setdefault("repositories", {})
    if args.action == "record":
        patterns = args.include or ["**/*"]
        files = hash_scope(repository, patterns)
        if not files:
            parser.error("The requested compatibility scope contains no files")
        snapshots[args.repository] = {
            "aggregate_sha256": aggregate_hash(files),
            "files": files,
            "formatter": {
                "branch": git_branch(project_root),
                "commit": git_value(project_root, "rev-parse", "HEAD"),
            },
            "include": patterns,
            "source": {
                "branch": git_branch(repository),
                "commit": git_value(repository, "rev-parse", "HEAD"),
            },
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Recorded {len(files)} files for {args.repository}")
        print(f"Aggregate SHA-256: {snapshots[args.repository]['aggregate_sha256']}")
        print(f"Report: {args.report}")
        return 0

    if args.include:
        parser.error("--include is only valid when recording")
    if args.repository not in snapshots:
        parser.error(f"No recorded snapshot for {args.repository}")
    issues = verify_snapshot(repository, snapshots[args.repository])
    if issues:
        print(f"Compatibility snapshot mismatch for {args.repository}:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    snapshot = snapshots[args.repository]
    print(
        f"Verified {len(snapshot['files'])} files for {args.repository}: "
        f"{snapshot['aggregate_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
