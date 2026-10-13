# IR-disabled-test-reason

Give disabled JUnit tests a nonempty reason.

- **Auto-Fixable**: No
- **Enabled by Default**: No
- **Category**: Documentation
- **Commit Profile**: No
- **Configuration Options**:
  - `enabled` (Default: `false`): Enable or disable this rule.
  - `severity` (Default: `warning`): Violation severity.

#### Default `WARNING_CONFIG`
- `severity`: `warning`

#### Default `WARNING_OPTION`
- `severity`: `{'default': 'warning', 'description': 'Violation severity.'}`

#### Executable Cases
##### missing disabled reason — Reported
```java
class SampleTest { @Disabled void waits() {} }

```

##### documented disabled test — Accepted
```java
class SampleTest { @Disabled("Waiting for replacement") void waits() {} }

```
