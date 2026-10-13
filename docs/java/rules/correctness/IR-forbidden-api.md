# IR-forbidden-api

Report explicitly configured Java imports, qualified references, and invocations.

- **Auto-Fixable**: No
- **Enabled by Default**: No
- **Category**: Correctness
- **Commit Profile**: No
- **Configuration Options**:
  - `enabled` (Default: `false`): Enable or disable this rule.
  - `severity` (Default: `warning`): Violation severity.
  - `symbols` (Default: `['System.gc']`): Exact import names or qualified source references to report.

#### Default `WARNING_CONFIG`
- `severity`: `warning`

#### Default `WARNING_OPTION`
- `severity`: `{'default': 'warning', 'description': 'Violation severity.'}`

#### Executable Cases
##### forbidden collection — Reported
```java
class Sample { void clean() { System.gc(); } }

```

##### ordinary collection — Accepted
```java
class Sample { void clean() { cleaner.run(); } Object cleaner; }

```
