# IR-redundant-imports

Remove duplicate, java.lang, and same-package imports.

- **Auto-Fixable**: Sometimes
- **Enabled by Default**: Yes
- **Category**: Imports
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
##### java lang import — Not Fixed
```java
package sample;
import java.lang.String;
class Sample {}

```

##### needed import — Accepted
```java
package sample;
import java.util.List;
class Sample {}

```
