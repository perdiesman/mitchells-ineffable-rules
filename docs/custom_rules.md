# Writing Custom Rules

Mitchell's Ineffable Rules (IR) Linter is designed to be fully modular and extensible. You can define custom rules for any language (including custom languages not supported out-of-the-box).

---

## 1. Directory Structure

Custom rules are loaded from directory structures representing the target language name. For example, if you have custom rules for `sql` and a custom language `foo`, organize your directory as follows:

```text
/my-custom-rules/
  ├── sql/
  │    ├── __init__.py           # Optional: Defines category display names
  │    ├── my_select_rule.py     # Custom SQL rule
  │    └── my_keyword_rule.py    # Custom SQL rule
  └── foo/
       ├── __init__.py           # Optional: Defines category display names
       └── custom_foo_rule.py    # Custom Foo rule
```

---

## 2. Rule Definition Interface

All rule classes must subclass `BaseRule` (imported from `mir.engine.rule_interface`).

### Required Fields & Methods
- **`rule_id`**: A unique string identifying the rule (e.g. `"IR-my-select-rule"`). Cannot be empty or `"IR-base"`.
- **`description`**: A short explanation of the rule's check (cannot be `"Base rule template"`).
- **`category`**: A string mapping the category of the rule. Categories determine how rules are grouped in the documentation and output.
- **`is_fixable`**: Must be one of `"yes"`, `"no"`, or `"sometimes"`.
- **`check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]`**:
  - Main check logic.
  - Takes the file content string, the absolute/relative file path, and a configuration dictionary.
  - Returns a list of `Violation` objects (from `mir.engine.rule_interface`).

### Optional Fields & Methods
- **`enabled_by_default`** (boolean, default: `True`): Controls whether the rule runs when not explicitly configured.
- **`default_config`** (dictionary, default: `{}`): Holds default configuration values for rule options.
- **`examples_violating`** (list of strings): Code snippet(s) demonstrating style violations.
- **`examples_correct`** (list of strings): Code snippet(s) showing correct format.
- **`fix(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> str`**:
  - Implements the correction logic.
  - Required if `is_fixable` is `"yes"` or `"sometimes"`.
  - Returns the modified code content string.

---

## 3. Custom Rule Template

Here is a full template for implementing a custom SQL rule:

```python
from typing import List, Dict, Any
from mir.engine.rule_interface import BaseRule, Violation

class MyCustomSqlRule(BaseRule):
    rule_id = "IR-my-custom-sql"
    description = "Checks that SELECT statements do not query all columns (*) from large tables."
    category = "select/view/materialized view"
    is_fixable = "no"
    enabled_by_default = True
    
    default_config = {
        "max_columns": 10
    }
    
    examples_violating = [
        "SELECT * FROM large_table;"
    ]
    examples_correct = [
        "SELECT id, name FROM large_table;"
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        # Implement check logic...
        # Fall back to default config if parameters are missing
        max_cols = rule_config.get("max_columns", self.default_config["max_columns"])
        
        # Example violation creation
        # violations.append(
        #     Violation(
        #         rule_id=self.rule_id,
        #         line_number=1,
        #         message="Do not query all columns.",
        #         offending_lines=["SELECT * FROM large_table;"]
        #     )
        # )
        return violations
```

---

## 4. How to Load and Execute Custom Rules

You can tell the linter about your custom rules using three methods:

### CLI Options
Use `--include-dir` to pass the path to your custom rules directory, and `--rule-mode` to select between extending or replacing:
```bash
# Extend built-in rules (default)
uv run mir/main.py --include-dir /my-custom-rules --rule-mode extend .

# Replace built-in rules (runs ONLY custom rules for the matching languages)
uv run mir/main.py --include-dir /my-custom-rules --rule-mode replace .
```

### Environment Variables
```bash
export IR_INCLUDE_DIRS="/my-custom-rules"
export IR_RULE_MODE="replace"
uv run mir/main.py .
```

### Configuration File (`.ir-config.yaml`)
```yaml
include_dirs:
  - /my-custom-rules
rule_mode: extend  # or replace
```

---

## 5. Strict Validation on Start

To ensure custom rules do not crash during execution or corrupt files, Mitchell's Ineffable Rules Linter runs a **strict validation check** on all custom rules as they are imported. 

If any custom rule has the following issues:
- Fails to compile or import due to Python syntax or runtime errors.
- Does not subclass `BaseRule`.
- Fails to implement required attributes (`rule_id`, `description`, `category`, `is_fixable`).
- Sets `is_fixable` to an invalid value (must be `"yes"`, `"no"`, or `"sometimes"`).
- Does not override the `check` method.
- Fails format check on optional config lists or dictionaries.

The linter will immediately print a `RuleValidationError` and exit with an error code (`1`), preventing any execution or linting until corrected.

---

## 6. Automatic Testing via Examples

To simplify development, the project includes an **embedded meta-testing framework** ([tests/test_meta_rules.py](file:///home/me/projects/mitchells-ineffable-rules/tests/test_meta_rules.py)). 

If you include your custom rule directory during testing (e.g. by configuring it or modifying the test run environment), the framework will automatically discover, load, and test your rules:
- It runs `check()` on each snippet in `examples_violating` and verifies it produces at least one violation.
- If `is_fixable` is `"yes"` or `"sometimes"`, it runs `fix()` on each violating snippet and asserts that the corrected output produces zero violations.
- It runs `check()` on each snippet in `examples_correct` and verifies it produces zero violations.

This ensures you can test your rule implementations immediately without having to write separate test scripts.

