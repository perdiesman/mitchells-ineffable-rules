# IR-javadoc-tags

Use canonical Javadoc block-tag order and nonempty descriptions.

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
##### empty return tag — Reported
```java
/**
 * Value.
 * @return
 */
class Sample {}

```

##### described return tag — Accepted
```java
/**
 * Value.
 * @return the value
 */
class Sample {}

```
