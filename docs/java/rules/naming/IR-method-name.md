# IR-method-name

Use lowerCamelCase Java method names.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: Naming
- **Commit Profile**: No
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `severity` (Default: `warning`): Violation severity.
  - `pattern` (Default: `[a-z][A-Za-z0-9]*`): Allowed method-name pattern.

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
##### uppercase method — Reported
```java
class Sample { void Execute() {} }

```

##### camel method — Accepted
```java
class Sample { void executeValue() {} }

```
