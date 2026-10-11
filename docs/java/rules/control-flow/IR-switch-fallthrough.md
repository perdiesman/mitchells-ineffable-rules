# IR-switch-fallthrough

Mark intentional fall-through in colon-style switch statement groups.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: Control Flow
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
##### unmarked fallthrough — Reported
```java
class Sample { void run(int value) { switch (value) { case 1: prepare(); case 2: execute(); break; } } void prepare() {} void execute() {} }

```

##### terminated group — Accepted
```java
class Sample { void run(int value) { switch (value) { case 1: prepare(); break; case 2: execute(); break; } } void prepare() {} void execute() {} }

```
