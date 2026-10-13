# IR-package-name

Use lowercase alphanumeric Java package components.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: Naming
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
##### uppercase package — Reported
```java
package sample.App;
class Sample {}

```

##### lowercase package — Accepted
```java
package sample.app;
class Sample {}

```
