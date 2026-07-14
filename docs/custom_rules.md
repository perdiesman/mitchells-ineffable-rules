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

### Defining Category Headers (`__init__.py`)

To customize the order and friendly display titles of rule categories in generated Markdown documentation and CLI details, define a `CATEGORIES` dictionary mapping category slugs to headers in your language's `__init__.py` file.

For example, inside `/my-custom-rules/foo/__init__.py`:
```python
CATEGORIES = {
    "general": "General Rules",
    "tags/elements": "Tags and Elements",
    "namespaces": "Namespaces and Scoping"
}
```
*Note: If a category is used in a rule but is omitted from `CATEGORIES`, the linter dynamically appends it at the end of the guide and formats the slug title automatically.*

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
- **`exclude_recursive`** (boolean, default: `False`): If `True`, excludes the rule from being executed recursively on PL/pgSQL function bodies. Use this for general rules (like line length or blank line counts) that run on the entire file content and do not require AST/tokenization recursive checks.
- **`only_recursive`** (boolean, default: `False`): If `True`, the rule is only run recursively on PL/pgSQL function bodies, and is skipped on the outer main file checking/fixing. Use this for rules that specifically format code structures unique to function bodies (like block-level indentations).
- **`default_config`** (dictionary, default: `{}`): Holds default configuration values for rule options.
- **`config_options`** (dictionary, default: `{}`): Declares detailed parameter options, descriptions, default values, and fallback instructions.
- **`examples`** (list of dictionaries): Paired violating/correct code snippets demonstrating formatting violations and corrections.
- **`additional_validations`** (list of strings): Compliant code statements that must always pass check verification and remain unchanged.
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
from mir.rules.sql.line_length import LineLengthRule

class MyCustomSqlRule(BaseRule):
    rule_id = "IR-my-custom-sql"
    description = "Checks that SELECT statements do not query all columns (*) from large tables."
    category = "select/view/materialized view"
    is_fixable = "no"
    enabled_by_default = True
    
    default_config = {}
    config_options = {
        "max_length": {
            "default": 120,
            "description": "Maximum line length limit.",
            "fallback": "IR-line-length:max_length"
        }
    }
    
    examples = [
        {
            "violating": "SELECT * FROM large_table;",
            "correct": "SELECT id, name FROM large_table;"
        }
    ]
    additional_validations = [
        "SELECT id, name FROM users;"
    ]

    def check(self, content: str, file_path: str, rule_config: Dict[str, Any]) -> List[Violation]:
        violations = []
        # Resolve config with fallback lookup support
        max_len = self.get_config_value(
            rule_config,
            "max_length",
            default_value=120,
            fallbacks=[(LineLengthRule, "max_length")]
        )
        # Implement check logic using max_len...
        return violations
```

### Configuration Value Fallbacks

If your rule depends on parameters managed by other rules (e.g. sharing indentation sizes or line length limits), you can avoid duplicate options by using `self.get_config_value`:

```python
val = self.get_config_value(
    rule_config,
    "local_param_name",
    default_value=default_val,
    fallbacks=[(OtherRuleClass, "other_param_name")]
)
```
The helper automatically queries the user's explicit overrides, checks the fallback rule's overrides (respecting language prefixes), and falls back to rule class defaults before using the local default.

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
- It runs `check()` on each snippet in `examples`' `violating` key and verifies it produces at least one violation.
- If `is_fixable` is `"yes"` or `"sometimes"`, it runs `fix()` on each violating snippet and asserts that the corrected output matches the paired `correct` snippet exactly and produces zero violations.
- It runs `check()` on each statement in `additional_validations` and verifies it produces zero violations and remains unchanged.

This ensures you can test your rule implementations immediately without having to write separate test scripts.
