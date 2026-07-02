#!/bin/bash

# git pre-commit hook for Mitchell's Ineffable Rules (IR) Linter
# To install:
#   cp pre-commit-hook.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit

IMAGE_NAME="mitchells-ineffable-rules:latest"

# 1. Get all staged files that are added (A), copied (C), or modified (M)
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM)

if [ -z "$STAGED_FILES" ]; then
    exit 0
fi

# 2. Filter for supported file extensions (.sql, .java, .xml)
TARGET_FILES=()
for file in $STAGED_FILES; do
    if [[ "$file" =~ \.(sql|java|jav|xml)$ ]]; then
        TARGET_FILES+=("$file")
    fi
done

# If no target files are staged, exit early
if [ ${#TARGET_FILES[@]} -eq 0 ]; then
    exit 0
fi

echo "Running Mitchell's Ineffable Rules Linter on staged files..."

# Check if docker image exists. If not, prompt user or build it.
if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    echo "Warning: Docker image '$IMAGE_NAME' not found."
    echo "Please build it first: docker build -t $IMAGE_NAME ."
    exit 1
fi

# 3. Run the linter via Docker
# We mount the current working directory to /workspace inside the container.
# All paths passed from git diff are relative to the repository root.
docker run --rm -v "$(pwd):/workspace" "$IMAGE_NAME" "${TARGET_FILES[@]}"
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "Linter violations found. Commit aborted."
    exit 1
fi

echo "Linter checks passed!"
exit 0
