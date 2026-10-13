#!/usr/bin/env bash
set -u

# Portable Git pre-commit hook for Mitchell's Ineffable Rules.

cleanup_docker_exchange() {
    if [[ -n ${MIR_HOOK_EXCHANGE:-} && -d $MIR_HOOK_EXCHANGE ]]; then
        rm -rf -- "$MIR_HOOK_EXCHANGE"
    fi
}

REPO_ROOT=$(git rev-parse --show-toplevel) || exit 1
cd "$REPO_ROOT" || exit 1

# MIR itself tracks development time in README. This block is skipped when
# the portable hook is copied into a consumer repository.
if [[ -f scripts/update_readme.py ]] && grep -q '^name = "mir-linter"' pyproject.toml 2>/dev/null; then
    python3 scripts/update_readme.py || exit 1
    git add README.md || exit 1
fi

run_host_mir() {
    if [[ -f mir/main.py ]] && grep -q '^name = "mir-linter"' pyproject.toml 2>/dev/null; then
        python3 -m mir.main --staged --fix
    elif command -v mir >/dev/null 2>&1; then
        mir --staged --fix
    else
        echo "MIR is not installed. Install mir-linter or use MIR_EXECUTION_MODE=docker." >&2
        return 1
    fi
}

run_docker_mir() {
    if ! command -v docker >/dev/null 2>&1; then
        echo "Docker is required when MIR_EXECUTION_MODE=docker." >&2
        return 2
    fi
    if ! command -v base64 >/dev/null 2>&1; then
        echo "The base64 command is required for the Docker hook exchange." >&2
        return 2
    fi

    local exchange manifest image document_id path entry mode extension path_base64
    local docker_status output index_info object_id changed_count index patch working_path
    local staged_size merged_worktree
    local -a document_ids document_paths document_modes
    exchange=$(mktemp -d "${TMPDIR:-/tmp}/mir-commit.XXXXXX") || return 2
    MIR_HOOK_EXCHANGE=$exchange
    trap cleanup_docker_exchange EXIT HUP INT TERM
    mkdir -p "$exchange/request" "$exchange/result"
    manifest="$exchange/request.jsonl"
    : > "$manifest"
    document_ids=()
    document_paths=()
    document_modes=()

    index=0
    while IFS= read -r -d '' path; do
        extension=".${path##*.}"
        extension=${extension,,}
        case "$extension" in
            .sql|.xml|.java|.jav|.py|.pyi|.js|.jsx|.mjs|.cjs|.ts|.tsx|.css|.scss|.html) ;;
            *) continue ;;
        esac
        entry=$(git ls-files -s -- "$path") || return 2
        mode=${entry%% *}
        case "$mode" in
            100644|100755) ;;
            *) continue ;;
        esac
        printf -v document_id '%06d' "$index"
        mkdir -p "$exchange/request/$document_id"
        git show ":$path" > "$exchange/request/$document_id/content" || return 2
        git diff --cached --unified=0 --no-color -- "$path" \
            > "$exchange/request/$document_id/diff" || return 2
        path_base64=$(printf '%s' "$path" | base64 | tr -d '\n')
        printf '%s\n' \
            "{\"schema_version\":1,\"id\":\"$document_id\",\"path_base64\":\"$path_base64\",\"mode\":\"$mode\",\"content_file\":\"request/$document_id/content\",\"diff_file\":\"request/$document_id/diff\"}" \
            >> "$manifest"
        document_ids+=("$document_id")
        document_paths+=("$path")
        document_modes+=("$mode")
        index=$((index + 1))
    done < <(git diff --cached --name-only -z --diff-filter=ACMR)

    if [[ ${#document_ids[@]} -eq 0 ]]; then
        return 0
    fi

    if [[ -d "$REPO_ROOT/.git" ]]; then
        mkdir "$exchange/hidden-git"
    else
        : > "$exchange/hidden-git"
    fi
    image=${MIR_DOCKER_IMAGE:-}
    if [[ -z $image ]]; then
        image=$(git config --get mir.dockerImage || true)
    fi
    image=${image:-mir-linter:latest}
    docker run --rm --network none --read-only \
        --cap-drop ALL --security-opt no-new-privileges \
        --user "$(id -u):$(id -g)" \
        --env HOME=/tmp --env RUFF_CACHE_DIR=/tmp/ruff-cache \
        --env MIR_CONTAINERIZED=1 \
        --volume "$REPO_ROOT:/workspace:ro" \
        --volume "$exchange/hidden-git:/workspace/.git:ro" \
        --volume "$exchange:/exchange:rw" \
        --tmpfs /tmp:rw,nosuid,nodev,size=128m \
        "$image" \
        --batch-manifest /exchange/request.jsonl \
        --batch-output /exchange/result \
        --profile commit --fix
    docker_status=$?
    if [[ $docker_status -gt 1 ]]; then
        echo "MIR Docker batch failed; the Git index was not changed." >&2
        return "$docker_status"
    fi

    index_info="$exchange/index-info"
    : > "$index_info"
    changed_count=0
    for index in "${!document_ids[@]}"; do
        document_id=${document_ids[$index]}
        output="$exchange/result/$document_id/content"
        [[ -f "$output" ]] || continue
        object_id=$(git hash-object -w --stdin < "$output") || return 2
        printf '%s %s\t%s\0' \
            "${document_modes[$index]}" "$object_id" "${document_paths[$index]}" \
            >> "$index_info"
        changed_count=$((changed_count + 1))
    done
    if [[ $changed_count -gt 0 ]]; then
        git update-index -z --index-info < "$index_info" || return 2
    fi

    for index in "${!document_ids[@]}"; do
        document_id=${document_ids[$index]}
        path=${document_paths[$index]}
        output="$exchange/result/$document_id/content"
        [[ -f "$output" ]] || continue
        working_path="$REPO_ROOT/$path"
        if [[ -f "$working_path" ]] && \
            cmp -s "$exchange/request/$document_id/content" "$working_path"; then
            cp -- "$output" "$working_path" || return 2
            continue
        fi
        staged_size=$(wc -c < "$exchange/request/$document_id/content")
        if [[ -f "$working_path" ]] && \
            head -c "$staged_size" "$working_path" | \
                cmp -s "$exchange/request/$document_id/content" -; then
            merged_worktree="$exchange/result/$document_id/merged-worktree"
            cp -- "$output" "$merged_worktree" || return 2
            tail -c "+$((staged_size + 1))" "$working_path" \
                >> "$merged_worktree" || return 2
            cp -- "$merged_worktree" "$working_path" || return 2
            continue
        fi
        patch="$exchange/result/$document_id/working-tree.patch"
        if [[ -f "$patch" ]] && git apply --check --whitespace=nowarn "$patch"; then
            git apply --whitespace=nowarn "$patch" || return 2
        else
            echo "Warning: $path: staged content fixed; overlapping unstaged edits were preserved unchanged" >&2
        fi
    done
    return "$docker_status"
}

echo "Formatting staged changes with MIR..."
execution_mode=${MIR_EXECUTION_MODE:-}
if [[ -z $execution_mode ]]; then
    execution_mode=$(git config --get mir.executionMode || true)
fi
case "${execution_mode:-host}" in
    host) run_host_mir ;;
    docker) run_docker_mir ;;
    *)
        echo "MIR_EXECUTION_MODE must be 'host' or 'docker'." >&2
        exit 2
        ;;
esac
