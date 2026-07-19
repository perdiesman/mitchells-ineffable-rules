#!/bin/bash

# git pre-push hook for Mitchell's Ineffable Rules (IR) Linter
# To install:
#   cp pre-push-hook.sh .git/hooks/pre-push
#   chmod +x .git/hooks/pre-push

# Run the update script to make sure the README timestamp matches the current time
python3 scripts/update_readme.py --push

# Check if README.md has been modified
if ! git diff --exit-code README.md >/dev/null; then
    echo "=========================================================="
    echo "WARNING: README.md timestamp was out of date."
    echo "It has been updated to the current developer session time."
    echo "Please commit the updated README.md and try pushing again."
    echo "=========================================================="
    exit 1
fi

exit 0
