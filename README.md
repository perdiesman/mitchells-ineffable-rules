# Mitchell's Ineffable Rules (IR) Linter

A modular, configurable linter and formatter for **SQL, XML, MyBatis, Trellis, Java, Python, and web source**. MIR can run native rules or coordinate Ruff, ESLint, and Prettier on files, standard input, or the exact snapshots staged in Git.

---

## Features

- **Extensible Rules Architecture**: Add language rules simply by adding Python rule modules under `mir/rules/<language>/`.
- **External Tool Providers**: Reuse Ruff, ESLint, and Prettier through a validated provider API instead of reimplementing their mature language engines.
- **User Styling Guides**: Detailed style guides explaining each rule, its configuration parameters, auto-fixability, and clean vs. violating examples under `docs/`.
- **Precedence-Aware Configuration**: Merges CLI flags, environment variables, and YAML config file settings:
  $$\text{CLI arguments} > \text{Environment variables} > \text{Config file} > \text{Defaults}$$
- **Granular Disable Comments**:
  - **Single-line disable** (disables a rule for the next non-comment code line):
    - SQL: `-- IR-rule-name`
    - Java: `// IR-rule-name`
    - XML: `<!-- IR-rule-name -->`
  - **Block disable** (disables a rule for a range of lines):
    - SQL: `-- IR-start-rule-name` ... `-- IR-end-rule-name`
    - Java: `// IR-start-rule-name` ... `// IR-end-rule-name`
    - XML: `<!-- IR-start-rule-name -->` ... `<!-- IR-end-rule-name -->`
- **Execution Modes**:
  - `check`: Validates files and reports all errors (default).
  - `fix`: Applies automatic corrections to fixable rules directly to files.
  - `dry-run`: Runs checks and generates unified diffs showing proposed fixes without modifying the source.
  - `verbose`: Prints rule descriptions and the offending lines along with errors.
- **Index-Safe Commit Formatting**: `--staged --fix` reads changed blobs from the Git index, expands changed lines to their enclosing SQL/MyBatis/Trellis construct, updates only the index, and preserves unrelated or partially staged working-tree edits.
- **Template-Aware SQL**: MyBatis placeholders, Trellis named/dotted binds, XML entities, and Trellis control directives are preserved. Template contexts run only rules that explicitly declare themselves safe.
- **Conservative Commit Profile**: `--profile commit` opts into fast, local, syntax-preserving rules; ordinary CLI defaults remain backward compatible.

---

## Directory Structure

```text
.
├── docs/                       # Language-specific Style Guides
│   ├── java/                   # Generated Java rule index and rule pages
│   ├── sql/                    # Generated SQL rule index and rule pages
│   └── xml/                    # Generated XML rule index and rule pages
├── Dockerfile                  # Containerization
├── README.md                   # This instruction manual
├── requirements.txt            # Locked runtime dependency inputs
├── pre-commit-hook.sh          # Portable staged-snapshot formatter hook
├── pre-push-hook.sh            # Read-only development-time verification
├── scripts/
│   └── update_readme.py        # Automation script to update README timestamp
├── mir/
│   ├── main.py                 # Core CLI Entrypoint
│   ├── engine/                 # Core engine mechanics
│   │   ├── config.py           # Precedence-aware configuration loader
│   │   ├── disabler.py         # Parsing and handling disable comments
│   │   ├── rule_interface.py   # BaseRule & Violation class structures
│   │   ├── rules_loader.py     # Dynamic imports of language rules
│   │   └── runner.py           # Processing workflow (Check, Fix, Dry-Run)
│   └── rules/                  # Language specific rules
│       ├── java/               # Tree-sitter Java rules and shared helpers
│       ├── sql/                # SQL and Trellis rules
│       └── xml/                # XML and MyBatis rules
└── tests/                      # Suite of unit & integration tests
    ├── test_config.py          # Tests config parser
    ├── test_disabler.py        # Tests comment disabler logic
    ├── test_runner.py          # Tests CLI runner integration
    └── rules/                  # Rule specific tests
        └── sql/
            ├── test_line_length.py
            └── test_keyword_case.py
```

---

## Setup & Local Usage

MIR requires Python 3.9 or newer. Ensure you have [uv](https://github.com/astral-sh/uv) or a compatible Python installed. Java parsing uses the compiled `tree-sitter` and `tree-sitter-java` wheels declared by the project; it does not invoke a JVM compiler during formatting. Install `mir-linter[python]` for Ruff support. Prettier and ESLint are resolved from the target project's `node_modules/.bin` unless an explicit executable is configured; MIR never downloads tools during a lint run.

### 1. Running Tests
You can run the full test suite using `uv`:
```bash
uv run --frozen python -m unittest discover -s tests -p "test_*.py"
```

### 2. Style Guides & Documentation

- **Custom Rules Guide**: Refer to the [Custom Rules Guide](docs/custom_rules.md) for details on writing your own custom linting rules, parameter interfaces, and execution validation.
- **Language Style Guides**: The language indexes and rule pages under `docs/sql/`, `docs/java/`, and `docs/xml/` are **automatically generated by the package** from code metadata. To compile and update these guides in sync with rule source definitions, run:

  ```bash
  # Generate style guides directly inside the 'docs/' directory
  uv run mir/main.py --help docs

  # Generate style guides inside a custom directory name
  uv run mir/main.py --help docs:my_rules_docs
  ```
  This scans all rule modules under `mir/rules/` and compiles the style guide markdown files directly.

### 2. Linting execution
```bash
# Check files (default path: current directory)
uv run mir/main.py

# Verbose check on a specific file path
uv run mir/main.py -v path/to/file.sql

# Safe auto-fixing rules on a directory (rewrites matching files)
uv run mir/main.py --fix path/to/file.sql

# Show dry-run diffs
uv run mir/main.py --dry-run path/to/file.sql

# Check only changed lines, expanded to safe enclosing constructs
uv run mir/main.py --lines 12-18 path/to/file.sql

# Format the exact staged snapshots with the conservative commit profile
uv run mir/main.py --staged --fix
```

### 3. Rules CLI Documentation & Help
You can query and inspect the list of rules and details directly from the command line:
```bash
# List all rules across all languages
uv run mir/main.py --help rules

# List only SQL rules
uv run mir/main.py --help rules:sql

# Show detailed documentation & examples for a specific rule across all languages
uv run mir/main.py --help IR-line-length

# Show detailed documentation for a specific rule inside a specific language
uv run mir/main.py --help sql:IR-keyword-case
```

---

## Docker Usage

Build and execute the linter entirely inside a containerized sandbox.

### 1. Build the Docker Image
```bash
docker build -t mitchells-ineffable-rules:latest .
```

### 2. Lint Files via Docker
Mount your workspace volume into `/workspace` in the container:
```bash
# Basic check on the current directory
docker run --rm -v "$(pwd):/workspace" mitchells-ineffable-rules:latest .

# Run auto-fixes
docker run --rm -v "$(pwd):/workspace" mitchells-ineffable-rules:latest --fix .

# Verbose dry-run on a file
docker run --rm -v "$(pwd):/workspace" mitchells-ineffable-rules:latest --dry-run -v query.sql
```

---

## Git Pre-commit Hook Integration

The included hook runs `mir --staged --fix`. Fixes are written to the Git index; an unrelated unstaged edit remains unstaged. If an unstaged edit overlaps a formatter edit, MIR leaves the working tree alone and reports that the index-only fix must be reviewed.

For this repository, use the tracked hooks:

```bash
git config core.hooksPath .githooks
```

For Web, AERIE, EAGLE-AI, or another consumer repository, install MIR in the active Python environment and copy the portable hook. See the [consumer hook guide](docs/commit-hook.md) for ready-to-run commands and configuration examples.

```bash
python3 -m pip install -e /path/to/mitchells-ineffable-rules
cp /path/to/mitchells-ineffable-rules/pre-commit-hook.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

The hook selects supported staged files itself; do not pass the output of `git diff` as filenames.

---

## Git Pre-push Hook Integration

MIR’s own tracked pre-commit hook updates and stages the development-time lines below. Its pre-push hook only verifies them and never mutates the worktree:

1. Copy the hook script into your repository's hook directory:
   ```bash
   cp pre-push-hook.sh .git/hooks/pre-push
   ```
2. Make sure it is executable:
   ```bash
   chmod +x .git/hooks/pre-push
   ```

Consumer repositories only need the pre-commit formatter hook; the time-tracking behavior activates only in this MIR repository.

---

## Java

Java formatting is syntax-aware and defaults to four-space block and continuation indents, a 120-column target, K&R braces, Java-first import groups, compact constructs when they fit, and one item per line when they do not. The commit profile applies only syntax-preserving source layout; broader naming, correctness, and Javadoc checks remain ordinary configurable rules. Semantic rewrites such as removing redundant boolean comparisons require an explicit `semantic_fix: true` rule setting and never run in the commit profile.

The structural layout rules cover declarations, annotated and ordinary parameter lists, argument lists, assignments, binary and ternary expressions, method chains, lambdas, switch expressions, loop headers, try-with-resources, arrays and annotation arrays, type clauses, type parameters, enums, and member spacing. Width-sensitive rules keep a construct on one line when it fits and use a stable syntax-aware continuation layout otherwise. The parser index is shared across repeated node queries so adding structural coverage does not require repeatedly walking the complete syntax tree.

Changed Java lines passed through `--lines` or `--staged` expand to the enclosing declaration or member before fixes run. String literals, character literals, text blocks, and comments are part of the commit safety signature. Text-block payload indentation is preserved because changing it can change the runtime string value. Generated sources are skipped by default using common generated paths, header markers, and `@Generated`; projects can select `check` or `format` instead:

The commit formatter can therefore leave an over-limit line when shortening it would require splitting a literal token, reflowing comment text, or editing generated code. The normal `IR-line-length` check still reports those lines for deliberate review; it is report-only and excluded from the commit profile so a safe formatting pass does not block the commit on content it is not authorized to rewrite.

```yaml
languages:
  java:
    generated:
      mode: skip # skip, check, or format
      path_patterns:
        - "**/target/generated-sources/**"
        - "**/build/generated/**"
        - "**/generated/**"
      header_markers:
        - "do not edit"
        - "generated source"
      annotations:
        - Generated
```

Every Java rule supplies generic executable cases used by both the generated [Java guide](docs/java/README.md) and the metadata-driven tests. Declaration-level suppressions use the same one-line and block comment syntax shown above. External Java rules still extend or replace the built-ins through `BaseRule` and the validated loader.

## Ruff, ESLint, and Prettier

External providers use the same file, stdin, line-selection, dry-run, and staged-index workflow as native MIR rules. Python runs Ruff lint fixes before Ruff formatting. JavaScript and TypeScript run ESLint fixes before Prettier; CSS, SCSS, and HTML use Prettier. JSON, YAML, Markdown, and Jupyter notebooks are intentionally outside the initial default scope.

MIR respects the nearest native tool configuration. Ruff discovers `pyproject.toml`, `ruff.toml`, and `.ruff.toml`; Prettier and ESLint use their project configuration and locally locked plugins. In `auto` mode an unavailable provider is skipped. An explicitly enabled provider without a usable executable is an error.

```yaml
providers:
  ruff:
    enabled: auto
    unsafe_fixes: false
  eslint:
    enabled: auto
    fix: true
  prettier:
    enabled: auto

languages:
  typescript:
    providers: [eslint, prettier]
```

Provider-level and native suppressions may coexist. `# IR-ruff:F401`, `// IR-start-prettier` / `// IR-end-prettier`, and `IR-all` are understood by MIR, while `noqa`, `ruff: disable`, `prettier-ignore`, and ESLint disable comments remain owned by their tools. See the [external provider guide](docs/external-providers.md) and generated [provider catalog](docs/providers/README.md).

## MyBatis and Trellis

MyBatis mapper elements (`select`, `insert`, `update`, `delete`, and reusable `sql` fragments) are expanded into source-mapped SQL. Safe edits map back into text nodes without touching XML tags, including SQL text beside inline MyBatis tags. MyBatis `#{value}` and `${identifier}` placeholders are opaque SQL parameters.

Trellis templates are detected from `-- trellis:` directives or named binds. MIR validates `if`/`elif`/`else`/`endif`, `choose`/`when`/`otherwise`/`endchoose`, and `for item in items separator=","`/`endfor`. Blocks are indented like programming-language control flow: conditional and loop bodies are one level deeper, while `when`/`otherwise` branches and their SQL nest beneath `choose`. Named binds such as `:item_id` and `:model.item_id` are opaque parameters. A Trellis template runs only rules whose metadata declares `trellis_safe = True`; external rules can opt in through the same `BaseRule` interface. PyGarden's generated SQL follows the same default layout and passes through the commit profile unchanged.

The commit profile rejects a proposed fix if it changes protected SQL syntax: template parameters, string literals, quoted identifiers, PostgreSQL cast target identity, or the operator sequence. For Trellis templates it also rejects removal, insertion, reordering, or expression changes in directive comments while permitting layout-only normalization. Cast target casing may be standardized by the datatype rule. The same SQL invariant is checked after staged-line filtering and after MyBatis edits are mapped back into XML.

Compatibility outputs that have completed manual review can be recorded in the ignored local report and checked for later formatter drift:

```bash
python scripts/prepare_compat.py
python scripts/compat_report.py record eagle_ai --include 'backend/src/eagle_ai/sql/**/*.sql'
python scripts/compat_report.py verify eagle_ai
python scripts/compat_report.py record web --root local/compat/java --report local/compat/java/report.json --include '**/*.java'
python scripts/compat_report.py verify web --root local/compat/java --report local/compat/java/report.json
```

The preparation script maintains ignored clones of Web, AERIE, EAGLE-AI, PyGarden's Trellis branch, and the Trellis FastAPI example under `local/compat/`; pass `--refresh` only when every clone is clean. The report stores the source and formatter commits, individual SHA-256 values, and a path-sensitive aggregate SHA-256. Verification reports changed, added, and missing files within the recorded scope.

---

## Configuration

You can create an `.ir-config.yaml` file in the root of your project:

```yaml
# Rules to globally disable
disable:
  - IR-some-disabled-rule

# Global flags
verbose: true
fix: false

# External rule directories (to extend or replace built-in rulesets)
include_dirs:
  - /path/to/my/custom_rules

# Rule mode for common languages: "extend" (default, built-in + custom) or "replace" (custom only)
rule_mode: extend

# External provider modules and tool orchestration
provider_dirs:
  - /path/to/my/providers
providers:
  ruff:
    enabled: auto
    unsafe_fixes: false
  prettier:
    enabled: auto
  eslint:
    enabled: auto
    fix: true

# Individual rule configuration
rules:
  IR-line-length:
    max_length: 120
  IR-in-exists:
    severity: warning # Override severity to warning (defaults to error if not specified)
```

### Configurable Severity (`severity`)

By default, any unfixable violation (or check-mode violation) is treated as an **error** and causes the linter to return a non-zero exit code. You can configure any rule to be treated as a **warning** instead by setting the `severity` config option to `warning` in `.ir-config.yaml`. Warnings are still printed to output, but they do not cause the linter to return a failure exit code.


### Rule Configuration Fallbacks

To keep rules independent and decoupled, certain rules can dynamically inherit configuration parameters from other rules if they are not explicitly set. 

For example, the SQL Column Layout formatter (`IR-column-layout`) dynamically falls back to query its parameters from the canonical rule configurations:
- `max_length` is inherited from the Line Length rule (`IR-line-length`)
- `indent_size` is inherited from the Indentation rule (`IR-indent`)

You can override these parameters specifically for the dependent rule or set them once on the canonical rule:
```yaml
rules:
  # Sets line length limit to 80 (affects both IR-line-length and IR-column-layout fallback)
  IR-line-length:
    max_length: 80

  # Specifically overrides column layout to use 100 instead
  IR-column-layout:
    max_length: 100
```

### Order of Precedence

Configuration parameters are merged with the following priority hierarchy (highest overrides lowest):
1. **Command Line Arguments** (e.g. `--fix`, `--disable IR-line-length`, `--include-dir /path`, `--rule-mode replace`)
2. **Environment Variables** (e.g. `IR_FIX=true`, `IR_DISABLE=IR-line-length`, `IR_INCLUDE_DIRS=/path`, `IR_RULE_MODE=replace`)
3. **YAML Config File** (e.g. `disable: [IR-line-length]`, `include_dirs: [/path]`, `rule_mode: replace` inside `.ir-config.yaml`)

---

## Writing Custom Rules

You can write custom rules to run against your codebase, either placing them inside the built-in rules directory or in an external custom rules directory. For full details on class specifications, default parameters, and strict execution validation, refer to the [Custom Rules Guide](docs/custom_rules.md). 

### 1. Built-in Directory
Create your rule Python module under `mir/rules/<language>/my_rule_name.py`.

### 2. External Directory
1. Create a directory structure, e.g. `/my-custom-rules/<language>/my_rule_name.py`.
2. Provide the path to the linter via CLI (`--include-dir /my-custom-rules`), Env (`IR_INCLUDE_DIRS`), or config (`include_dirs: ["/my-custom-rules"]`).
3. Set the `--rule-mode` to specify whether custom rules should **extend** (default) or **replace** the built-in rule sets.

### Custom Rule Implementation Example
Each custom rule must subclass `BaseRule` (from `mir.engine.rule_interface`):

```python
from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation

class MyXmlRule(BaseRule):
    rule_id = "IR-xml-rule"
    description = "A custom description of my rule."
    category = "general"
    is_fixable = "yes"  # "yes", "no", or "sometimes"

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        # Implement check logic...
        # If a violation is found, append Violation(...) to list.
        return violations

    def fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str:
        # If is_fixable is "yes" or "sometimes", return the modified content string
        return content
```

---

## Publishing to PyPI

For instructions on building distribution archives, TestPyPI validation, and publishing to the live Python Package Index, refer to the [PyPI Publishing Guide](docs/publishing.md).

---

*This package has been developed with **Antigravity** and **OpenAI Codex**.*

*Total Cumulative Development Time: ~63.0 hours*

*Last Developer Session: 2026-10-12T12:37:00Z*
