# IR-empty-catch

Explain or handle intentionally ignored exceptions.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: Correctness
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
##### empty catch — Reported
```java
class Sample { void run() { try { execute(); } catch (Exception exception) {} } void execute() {} }

```

##### explained catch — Accepted
```java
class Sample { void run() { try { execute(); } catch (Exception exception) { /* intentionally ignored */ } } void execute() {} }

```
