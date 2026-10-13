# IR-array-type-style

Attach array brackets to the type rather than the variable name.

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
##### C-style array — Reported
```java
class Sample { String values[]; }

```

##### type-style array — Accepted
```java
class Sample { String[] values; }

```
