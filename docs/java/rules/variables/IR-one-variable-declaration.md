# IR-one-variable-declaration

Declare one field or local variable per declaration outside for-loop headers.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: Variables and Fields
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
##### multiple fields — Reported
```java
class Sample { int first, second; }

```

##### separate fields — Accepted
```java
class Sample { int first; int second; }

```
