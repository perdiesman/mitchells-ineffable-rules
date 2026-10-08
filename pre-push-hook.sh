#!/usr/bin/env bash
set -u

# git pre-push hook for Mitchell's Ineffable Rules (IR) Linter
# To install:
#   cp pre-push-hook.sh .git/hooks/pre-push
#   chmod +x .git/hooks/pre-push

# Verification is deliberately read-only; pre-commit owns README updates.
REPO_ROOT=$(git rev-parse --show-toplevel) || exit 1
cd "$REPO_ROOT" || exit 1
python3 scripts/update_readme.py --check
