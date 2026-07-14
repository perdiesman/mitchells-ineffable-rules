# IR-line-length

Lines must not exceed the configured maximum length.

- **Auto-Fixable**: Sometimes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum line length limit.
  - `base_indent` (Default: `0`): Base indentation offset (in spaces or leading space string) to subtract before checking line lengths. *Note: Value dynamically inherited from rule [`IR-indent`](../general/IR-indent.md) -> `base_indent` if not configured.*

#### ❌ Violating Example
```sql
-- This is a very long comment line that exceeds the maximum line length limit of 120 characters to demonstrate how the comment wrapping works.
```

####  Correct Example
```sql
-- This is a very long comment line that exceeds the maximum line length limit of 120 characters to demonstrate how the
-- comment wrapping works.
```
