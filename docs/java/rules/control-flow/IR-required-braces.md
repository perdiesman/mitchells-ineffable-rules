# IR-required-braces

Use braces for if, else, for, while, and do bodies.

- **Auto-Fixable**: Sometimes
- **Enabled by Default**: Yes
- **Category**: Control Flow
- **Commit Profile**: No
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `severity` (Default: `warning`): Violation severity.
  - `semantic_fix` (Default: `false`): Allow the optional source rewrite in normal --fix mode.

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
##### unbraced if — Not Fixed
```java
class Sample { void run(boolean ready) { if (ready) execute(); } void execute() {} }

```

##### braced if — Accepted
```java
class Sample { void run(boolean ready) { if (ready) { execute(); } } void execute() {} }

```
