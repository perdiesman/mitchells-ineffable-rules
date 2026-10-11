# IR-type-name

Use UpperCamelCase Java type names.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: Naming
- **Commit Profile**: No
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `severity` (Default: `warning`): Violation severity.
  - `pattern` (Default: `[A-Z][A-Za-z0-9]*`): Allowed type-name pattern.

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
##### lowercase type — Reported
```java
class sample {}

```

##### camel type — Accepted
```java
class SampleValue {}

```
