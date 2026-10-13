# Staged Commit Hook

MIR can format the exact SQL, XML, Java, Python, JavaScript, TypeScript, stylesheet, and HTML snapshots in Git's index:

```bash
mir --staged --fix
```

`--staged` automatically enables the conservative `commit` profile. Changed lines are expanded to the enclosing SQL statement, Trellis block, MyBatis statement element, or Java declaration/member. MIR writes successful fixes back to the index and does not stage unrelated working-tree changes.

The profile treats MyBatis placeholders and Trellis named binds as opaque. It also verifies that fixes preserve string literals, quoted identifiers, PostgreSQL cast target identity, and operator sequences. Cast target casing may be standardized by the datatype rule. An edit that violates those invariants is rejected with an explicit diagnostic instead of being written to the index.

For Java, the profile verifies the parsed token and comment sequence after every formatting rule and rejects output with parser errors. It preserves string/character literals and text blocks byte-for-byte, skips generated sources by default, and excludes semantic best-practice rewrites. Java's report-only 120-column check is also outside the commit profile until all remaining syntax forms have automatic wrapping support.

For external providers, MIR sends the staged blob rather than the working-tree file. Ruff and ESLint fixes must be anchored in the authorized changed range, while Ruff and Prettier range formatting may expand only to the enclosing logical statement. Disabled regions and unrelated staged lines remain protected. Provider failures and rejected edits are reported instead of falling back to whole-file writes.

Install Ruff with `mir-linter[python]`. Prettier and ESLint must be installed and locked in the consumer project; the hook never invokes a network-installing `npx` fallback. Use an exact provider `required_version` when the lockfile alone is not sufficient for the hook environment.

## Install in a consumer repository

Set the MIR checkout once, install it into the Python environment used for commits, and copy the portable hook:

```bash
MIR_ROOT=/path/to/mitchells-ineffable-rules
python3 -m pip install -e "$MIR_ROOT"
cp "$MIR_ROOT/pre-commit-hook.sh" .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

Run a review pass before relying on the hook:

```bash
mir --staged --dry-run
mir --staged --fix
git diff --cached --check
git diff --cached
```

The same commands can be run from these intended first consumers after replacing `MIR_ROOT`:

```bash
cd ~/projects/eaglei/webstack/web
# install/copy commands above

cd ~/projects/eaglei/webstack/aerie
# install/copy commands above

cd ~/projects/eaglei/eagle_ai
# install/copy commands above

cd ~/projects/eaglei/ong-analytics
git switch feature/EI-8398-mir-linter
# install/copy commands above
```

No consumer-specific SQL is stored in MIR's documentation or tests. Compatibility scans use ignored local clones only.

## Docker-backed hook

The portable hook can keep Git and the index entirely on the host while running MIR in a locked-down container. This mode requires Git, Docker, and the standard `base64` command on the host; it does not require a host Python or MIR installation.

Build the image once and configure each consumer repository:

```bash
MIR_ROOT=/path/to/mitchells-ineffable-rules
docker build -t mir-linter:latest "$MIR_ROOT"
cp "$MIR_ROOT/pre-commit-hook.sh" .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
git config mir.executionMode docker
git config mir.dockerImage mir-linter:latest
```

`MIR_EXECUTION_MODE` and `MIR_DOCKER_IMAGE` can temporarily override those repository settings. To return to a host installation, run `git config mir.executionMode host`.

For each commit, the host hook:

1. Uses Git to collect supported staged paths, modes, exact staged blobs, and zero-context changed-line diffs.
2. Starts one container for the complete batch. The repository is mounted read-only, and an empty mount hides its `.git` directory or worktree pointer.
3. Passes only an isolated exchange directory as writable state. The container has no Git client and cannot update the index itself.
4. Hashes successful formatted blobs and updates the host index, then applies the same patch to the working tree only when it does not overlap unstaged work.

The container runs without network access, Linux capabilities, or privilege escalation. It uses the host user and group IDs so returned files have the correct ownership. Ruff is installed in the image. A Node.js runtime is present for Prettier and ESLint, while the provider packages and configuration still come from the consumer repository's locked `node_modules`.

External rule and provider directories used by Docker mode must be inside the mounted repository. The batch exchange accepts UTF-8 regular files; unsupported extensions, symlinks, submodules, and non-UTF-8 content are skipped just as non-source inputs.

## Optional configuration

Normal command-line behavior remains unchanged. The hook's commit profile focuses on conservative SQL token formatting, XML validity/attribute quoting, MyBatis source-mapped SQL, Trellis directives, and syntax-preserving Java layout. Project overrides still use `.ir-config.yaml`:

```yaml
rules:
  IR-keyword-case:
    enabled: true
  IR-trellis-directives:
    enabled: true
  java:IR-indent:
    indent_size: 4

languages:
  java:
    generated:
      mode: skip
```

External rules remain supported with `include_dirs` and `rule_mode`. A SQL rule must explicitly set `commit_profile = True`, and must also set `embedded_safe = True` for MyBatis or `trellis_safe = True` for Trellis before it can run in those contexts.

## Partial staging behavior

- Non-overlapping unstaged edits are preserved in the working tree while the staged blob is formatted.
- Overlapping unstaged edits are never silently staged or overwritten. MIR updates the index, leaves the worktree untouched, and prints a warning.
- Unfixable errors in the changed construct block the commit. Existing errors outside the authorized changed scope do not.
- PostgreSQL operators such as `->`, `->>`, `#>`, `#>>`, `=>`, and `:=` remain atomic when spacing is normalized, including their XML-escaped MyBatis forms.
