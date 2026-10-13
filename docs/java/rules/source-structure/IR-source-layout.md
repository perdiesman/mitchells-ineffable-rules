# IR-source-layout

Separate package, import, and top-level type sections with one blank line.

- **Auto-Fixable**: Sometimes
- **Enabled by Default**: Yes
- **Category**: Source Structure
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled`: `true`

#### Executable Cases
##### package and imports — Fixed
```java
package sample.app;
import java.util.List;
class Sample {}

```

Expected fixed output:
```java
package sample.app;

import java.util.List;

class Sample {}

```

##### canonical sections — Accepted
```java
package sample.app;

import java.util.List;

class Sample {}

```
