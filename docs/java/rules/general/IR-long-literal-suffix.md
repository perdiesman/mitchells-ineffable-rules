# IR-long-literal-suffix

Use an uppercase L suffix for long integer literals.

- **Auto-Fixable**: Sometimes
- **Enabled by Default**: Yes
- **Category**: General Rules
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
##### lowercase suffix — Not Fixed
```java
class Sample { long value = 25l; }

```

##### uppercase suffix — Accepted
```java
class Sample { long value = 25L; }

```
