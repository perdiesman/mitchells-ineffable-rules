#!/usr/bin/env python3
"""Prepare ignored compatibility clones at stable remote branch tips."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Repository:
    name: str
    url: str
    branch: str


REPOSITORIES = (
    Repository("web", "git@code.ornl.gov:eagle-i/web.git", "develop"),
    Repository("aerie", "git@code.ornl.gov:eagle-i/aerie.git", "develop"),
    Repository("eagle_ai", "git@code.ornl.gov:eagle-i/eagle-ai.git", "develop"),
    Repository("pygarden", "https://github.com/ORNL/pygarden.git", "feature/trellis"),
)


def run(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        args,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def ensure_clone(repository: Repository, root: Path, refresh: bool) -> dict[str, str]:
    destination = root / repository.name
    if not destination.exists():
        run(
            "git",
            "clone",
            "--single-branch",
            "--branch",
            repository.branch,
            repository.url,
            str(destination),
        )
    elif not (destination / ".git").exists():
        raise RuntimeError(f"Compatibility path is not a Git repository: {destination}")
    elif refresh:
        status = run("git", "status", "--porcelain", cwd=destination)
        if status:
            raise RuntimeError(f"Refusing to refresh dirty compatibility clone: {destination}")
        run("git", "fetch", "origin", repository.branch, cwd=destination)
        run("git", "switch", repository.branch, cwd=destination)
        run("git", "merge", "--ff-only", f"origin/{repository.branch}", cwd=destination)

    return {
        "branch": run("git", "branch", "--show-current", cwd=destination),
        "commit": run("git", "rev-parse", "HEAD", cwd=destination),
        "path": str(destination.resolve()),
        "remote": repository.url,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "local" / "compat",
        help="Destination for ignored compatibility clones.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Fast-forward clean existing clones to their current remote branch tips.",
    )
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)

    manifest = {
        repository.name: ensure_clone(repository, args.root, args.refresh)
        for repository in REPOSITORIES
    }
    manifest_path = args.root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"Wrote compatibility manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
