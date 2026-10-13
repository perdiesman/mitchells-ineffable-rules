# IR-public-api-javadoc

Document public and protected top-level types and members.

- **Auto-Fixable**: No
- **Enabled by Default**: No
- **Category**: Documentation
- **Commit Profile**: No
- **Configuration Options**:
  - `enabled` (Default: `false`): Enable or disable this rule.
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
##### undocumented public type — Reported
```java
public class Sample {}

```

##### documented public type — Accepted
```java
/** Generic sample type. */
public class Sample {}

```
