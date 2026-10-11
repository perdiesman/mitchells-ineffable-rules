# IR-overload-grouping

Keep methods and constructors with the same name in contiguous groups.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: Method Declarations
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
##### split overloads — Reported
```java
class Sample { void run() {} void pause() {} void run(int count) {} }

```

##### grouped overloads — Accepted
```java
class Sample { void run() {} void run(int count) {} void pause() {} }

```
