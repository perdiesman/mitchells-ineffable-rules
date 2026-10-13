# IR-console-output

Use project logging instead of console output or printStackTrace.

- **Auto-Fixable**: No
- **Enabled by Default**: No
- **Category**: Correctness
- **Commit Profile**: No
- **Configuration Options**:
  - `enabled` (Default: `false`): Enable or disable this rule.
  - `severity` (Default: `warning`): Violation severity.

#### Default `WARNING_CONFIG`
- `severity`: `warning`

#### Default `WARNING_OPTION`
- `severity`: `{'default': 'warning', 'description': 'Violation severity.'}`

#### Executable Cases
##### standard output — Reported
```java
class Sample { void run() { System.out.println("value"); } }

```

##### print stack trace — Reported
```java
class Sample { void run(Exception problem) { problem.printStackTrace(); } }

```

##### ordinary call — Accepted
```java
class Sample { void run() { logger.info("value"); } Object logger; }

```
