# IR-interrupted-exception

Propagate InterruptedException or visibly restore the thread interruption flag.

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
##### swallowed interruption — Reported
```java
class Sample { void waitForWork() { try { run(); } catch (InterruptedException exception) { log(exception); } } void run() throws InterruptedException {} void log(Exception value) {} }

```

##### restored interruption — Accepted
```java
class Sample { void waitForWork() { try { run(); } catch (InterruptedException exception) { Thread.currentThread().interrupt(); } } void run() throws InterruptedException {} }

```
