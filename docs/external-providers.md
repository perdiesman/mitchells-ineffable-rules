# External Tool Providers

MIR providers adapt established tools to MIR's configuration, diagnostics, line selection, dry-run, and staged-index guarantees. Native language rules continue to subclass `BaseRule`; providers subclass `BaseProvider` and do not replace the rule loader.

## Resolution and trust

Ruff resolves from an explicit path, a nearby project virtual environment, or the active environment supplied by the `python` extra. Prettier and ESLint resolve from the nearest project-local `node_modules/.bin` or an explicit path. MIR does not download tools or plugins during execution.

Native Python and JavaScript configuration files may execute or load project code. Run providers only in repositories whose configuration and dependencies you trust.

## Configuration

Provider settings use the normal CLI, environment, YAML, and default precedence. `enabled` accepts `auto`, `true`, or `false`. Auto providers run when their executable is available; missing explicitly enabled providers fail the run.

```yaml
provider_dirs:
  - tools/mir-providers

providers:
  ruff:
    enabled: auto
    executable: auto
    config: discover
    check: true
    format: true
    unsafe_fixes: false
    timeout_seconds: 30
  eslint:
    enabled: auto
    executable: auto
    config: discover
    check: true
    fix: true
  prettier:
    enabled: auto
    executable: auto
    config: discover
```

Use `--enable-provider`, `--disable-provider`, and `--provider-dir` for command-line overrides. Equivalent environment variables are `IR_ENABLE_PROVIDERS`, `IR_DISABLE_PROVIDERS`, and `IR_PROVIDER_DIRS`.

## Adding a provider

An external provider package registers a `BaseProvider` subclass in the `mir.providers` entry-point group. A local provider directory may contain Python modules defining the same subclasses. Every provider declares a unique ID, languages, extensions, capabilities, defaults, configuration metadata, generic executable cases, and `run()` implementation. The validated loader rejects duplicate or incomplete providers before source processing begins.

Provider results contain structured findings, offset-based edits, diagnostics, and formatted content. Providers must never write source files directly. MIR remains responsible for authorization, index updates, dry-run diffs, warning/error policy, and persistence.

## Compatibility defaults

- EAGLE-AI: Ruff uses Python 3.12, 130 columns, its selected `E/F/I/UP/B/SIM` families, and its `SIM117` exception.
- PyGarden: Ruff uses 120 columns and its committed source/test inclusions, documentation, naming, and complexity selections.
- Trellis FastAPI: Ruff uses 120 columns and honors the generated-source exclusion.
- Web: Prettier and ESLint use the committed frontend configuration, ignore file, plugins, and lockfile-resolved versions.
- EAGLE-AI frontend: Node providers remain an auto-skip until the project installs them or configures an executable.

Compatibility repositories are ignored inputs. MIR documentation and tests use generic examples only.
