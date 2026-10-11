# IR-modifier-order

Use the standard Java modifier order.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Source Structure
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled`: `true`

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
##### unordered modifiers — Fixed
```java
final public static class Sample {}

```

Expected fixed output:
```java
public static final class Sample {}

```

##### ordered modifiers — Accepted
```java
public static final class Sample {}

```
