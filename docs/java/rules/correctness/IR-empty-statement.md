# IR-empty-statement

Do not use an accidental empty statement as a control-flow body.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: Correctness
- **Commit Profile**: No
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
##### empty if — Reported
```java
class Sample { void run(boolean ready) { if (ready); } }

```

##### empty block — Accepted
```java
class Sample { void run(boolean ready) { if (ready) {} } }

```
