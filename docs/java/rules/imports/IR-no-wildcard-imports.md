# IR-no-wildcard-imports

Use explicit imports instead of wildcard imports.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: Imports
- **Commit Profile**: No
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `severity` (Default: `warning`): Violation severity.

#### Executable Cases
##### wildcard import — Reported
```java
import sample.api.*;
class Sample {}

```

##### explicit import — Accepted
```java
import sample.api.Value;
class Sample {}

```
