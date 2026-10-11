# IR-redundant-boolean-comparison

Avoid explicit comparisons with true or false when the boolean expression is clear.

- **Auto-Fixable**: Sometimes
- **Enabled by Default**: Yes
- **Category**: Expressions
- **Commit Profile**: No
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `severity` (Default: `warning`): Violation severity.
  - `semantic_fix` (Default: `false`): Allow the optional source rewrite in normal --fix mode.

#### Default `SEMANTIC_CONFIG`
- `semantic_fix`: `False`
- `severity`: `warning`

#### Default `SEMANTIC_OPTIONS`
- `semantic_fix`: `{'default': False, 'description': 'Allow the optional source rewrite in normal --fix mode.'}`
- `severity`: `{'default': 'warning', 'description': 'Violation severity.'}`

#### Default `WARNING_CONFIG`
- `severity`: `warning`

#### Default `WARNING_OPTION`
- `severity`: `{'default': 'warning', 'description': 'Violation severity.'}`

#### Executable Cases
##### true comparison — Not Fixed
```java
class Sample { boolean run(boolean ready) { return ready == true; } }

```

##### direct boolean — Accepted
```java
class Sample { boolean run(boolean ready) { return ready; } }

```
