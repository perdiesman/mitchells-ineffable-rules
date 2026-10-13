# IR-finally-control-flow

Do not abruptly return, throw, break, or continue from a finally block.

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
##### return from finally — Reported
```java
class Sample { int read() { try { return 1; } finally { return 2; } } }

```

##### ordinary cleanup — Accepted
```java
class Sample { int read() { try { return 1; } finally { cleanup(); } } void cleanup() {} }

```

##### nested lambda return — Accepted
```java
class Sample { void read() { try {} finally { Runnable value = () -> { return; }; } } }

```
