# IR-import-order

Sort imports into static, platform, third-party, and project groups.

- **Auto-Fixable**: Sometimes
- **Enabled by Default**: Yes
- **Category**: Imports
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `project_prefixes` (Default: `[]`): Package prefixes placed in the project import group; the current package is inferred when empty.

#### Executable Cases
##### grouped imports — Fixed
```java
package sample.app;

import sample.shared.Value;
import java.util.List;
import static java.util.Collections.emptyList;

class Sample {}

```

Expected fixed output:
```java
package sample.app;

import static java.util.Collections.emptyList;

import java.util.List;

import sample.shared.Value;

class Sample {}

```

##### canonical imports — Accepted
```java
package sample.app;

import java.util.List;

import sample.shared.Value;

class Sample {}

```
