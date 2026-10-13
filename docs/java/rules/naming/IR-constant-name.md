# IR-constant-name

Use UPPER_SNAKE_CASE for configured static-final constant declarations.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: Naming
- **Commit Profile**: No
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `severity` (Default: `warning`): Violation severity.
  - `pattern` (Default: `[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*`): Allowed constant-name pattern.
  - `ignored_names` (Default: `['serialVersionUID']`): Static-final field names exempt from the rule.

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
##### camel constant — Reported
```java
class Sample { static final int maxCount = 3; }

```

##### snake constant — Accepted
```java
class Sample { static final int MAX_COUNT = 3; }

```
