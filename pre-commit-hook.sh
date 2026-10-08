#!/usr/bin/env bash
set -u

# Portable Git pre-commit hook for Mitchell's Ineffable Rules.

REPO_ROOT=$(git rev-parse --show-toplevel) || exit 1
cd "$REPO_ROOT" || exit 1

# MIR itself tracks development time in README. This block is skipped when
# the portable hook is copied into a consumer repository.
if [[ -f scripts/update_readme.py ]] && grep -q "Mitchell's Ineffable Rules" README.md 2>/dev/null; then
    python3 scripts/update_readme.py || exit 1
    git add README.md || exit 1
fi

echo "Formatting staged SQL and XML changes with MIR..."
if [[ -f mir/main.py ]]; then
    python3 -m mir.main --staged --fix
elif command -v mir >/dev/null 2>&1; then
    mir --staged --fix
else
    echo "MIR is not installed. Install mir-linter or edit pre-commit-hook.sh with the project command." >&2
    exit 1
fi
