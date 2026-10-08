# Staged Commit Hook

MIR can format the exact SQL and XML snapshots in Git's index:

```bash
mir --staged --fix
```

`--staged` automatically enables the conservative `commit` profile. Changed lines are expanded to the enclosing SQL statement, Trellis block, or MyBatis statement element. MIR writes successful fixes back to the index and does not stage unrelated working-tree changes.

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
```

No consumer-specific SQL is stored in MIR's documentation or tests. Compatibility scans use ignored local clones only.

## Optional configuration

Normal command-line behavior remains unchanged. The hook's commit profile currently focuses on conservative SQL token formatting, XML validity/attribute quoting, MyBatis source-mapped SQL, and Trellis directives. Project overrides still use `.ir-config.yaml`:

```yaml
rules:
  IR-keyword-case:
    enabled: true
  IR-trellis-directives:
    enabled: true
```

External rules remain supported with `include_dirs` and `rule_mode`. A SQL rule must explicitly set `commit_profile = True`, and must also set `embedded_safe = True` for MyBatis or `trellis_safe = True` for Trellis before it can run in those contexts.

## Partial staging behavior

- Non-overlapping unstaged edits are preserved in the working tree while the staged blob is formatted.
- Overlapping unstaged edits are never silently staged or overwritten. MIR updates the index, leaves the worktree untouched, and prints a warning.
- Unfixable errors in the changed construct block the commit. Existing errors outside the authorized changed scope do not.
