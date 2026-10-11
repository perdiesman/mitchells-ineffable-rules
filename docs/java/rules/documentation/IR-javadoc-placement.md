# IR-javadoc-placement

Place Javadoc before declaration annotations.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: Documentation
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
##### Javadoc after annotation — Reported
```java
@Deprecated
/** Old type. */
class Sample {}

```

##### Javadoc before annotation — Accepted
```java
/** Old type. */
@Deprecated
class Sample {}

```
