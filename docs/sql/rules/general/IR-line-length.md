# IR-line-length

Lines must not exceed the configured maximum length. Overlong keyword-owned IN, VALUES, and TABLE lists wrap one item per line, and long foreign-key constraints wrap their detail clauses. Large repeated one-row INSERT data dumps remain compact. Literal data that cannot be wrapped without changing its value is reported as nonfixable.

- **Auto-Fixable**: Sometimes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: No
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum line length limit.
  - `base_indent` (Default: `0`): Base indentation offset (in spaces or leading space string) to subtract before checking line lengths. *Note: Value dynamically inherited from rule [`IR-indent`](../general/IR-indent.md) -> `base_indent` if not configured.*
  - `bulk_insert_threshold` (Default: `100`): Number of repeated one-row INSERT statements that marks a file as a bulk data dump; use 0 to disable the exemption.

#### ❌ Violating Example
```sql
-- This is a very long comment line that exceeds the maximum line length limit of 120 characters to demonstrate how the comment wrapping works.
```

####  Correct Example
```sql
-- This is a very long comment line that exceeds the maximum line length limit of 120 characters to demonstrate how the
-- comment wrapping works.
```
