# IR-equals-hash-code

Declare equals and hashCode together in concrete Java classes.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: Correctness
- **Commit Profile**: No
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `severity` (Default: `warning`): Violation severity.

#### Default `WARNING_CONFIG`
- `severity`: `warning`

#### Default `WARNING_OPTION`
- `severity`: `{'default': 'warning', 'description': 'Violation severity.'}`

#### Executable Cases
##### equals without hash code — Reported
```java
class Sample { public boolean equals(Object value) { return false; } }

```

##### complete equality contract — Accepted
```java
class Sample { public boolean equals(Object value) { return false; } public int hashCode() { return 1; } }

```
