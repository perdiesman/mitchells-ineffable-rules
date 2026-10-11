# IR-assignment-in-condition

Avoid assignments inside control-flow conditions.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: Correctness
- **Commit Profile**: No
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `severity` (Default: `warning`): Violation severity.

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
##### assignment condition — Reported
```java
class Sample { void run(boolean ready) { if (ready = next()) {} } boolean next() { return true; } }

```

##### comparison condition — Accepted
```java
class Sample { void run(int value) { if (value == next()) {} } int next() { return 1; } }

```
