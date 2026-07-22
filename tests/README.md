# Tests Directory

This directory contains the automated test suite for the linter engine and its rules.

## Testing Architecture

The test suite is divided into two primary parts:

### 1. Embedded Rule Meta-Testing (`test_meta_rules.py`)
Rather than maintaining separate test files for every single rule, each rule contains its own unit tests directly embedded inside the rule class definition via the following class properties:
- **`examples`**: A list of dicts defining `violating` code blocks and their corresponding `correct` blocks.
- **`additional_validations`**: A list of valid code snippets that must pass the rule with zero violations.

The **`TestMetaRules`** test case automatically discovers all rules across all supported languages and verifies:
- **Violation Checking**: The `violating` example produces at least one violation.
- **Fix Correctness**: The `fix()` method transforms the `violating` code into exactly the `correct` code.
- **Post-Fix Safety**: The corrected code produces zero violations.
- **Idempotency**: Running `fix()` on corrected code a second time does not change the content.
- **Ruleset Idempotency**: Running all active rules recursively on the snippets converges to a stable state within 5 passes, ensuring no conflicting formatting loops exist.

**Guideline**: When writing or modifying a rule, always add its test cases directly to the rule's class definition.

### 2. Engine-Level Integration Testing (`test_runner.py`)
This file tests integration, execution, and parser engine behaviors using the runner API (`run_linter`), including:
- **CLI Options**: Validating `--fix`, `--disable-all`, `--rules-to-enable`, and `--quiet-warnings`.
- **Indentation Handling**: Base indentation auto-detection and indentation rule overlays.
- **Line/Block Filtering**: Verifying `--lines` filtering for targeted line ranges.
- **Host-Guest Embedding (MyBatis XML)**: Validating how SQL queries inside XML structures are extracted, formatted, mapped back to XML, and synced without parsing errors or indentation drift.

## Running the Tests

To run the full test suite, execute:
```bash
uv run python -m unittest discover tests
```

To run a specific test module:
```bash
uv run python -m unittest tests/test_meta_rules.py
uv run python -m unittest tests/test_runner.py
```
