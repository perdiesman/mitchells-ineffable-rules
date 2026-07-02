# IR-indent

Indent should be equal amounts of spaces (default 4).

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `indent_size` (Default: `4`): Indentation size in spaces.
  - `base_indent` (Default: `0`): Base indentation level (in spaces or leading space string) to expect for all lines.

#### ❌ Violating Example
```sql
SELECT
  id,
   name
FROM users;
```

####  Correct Example
```sql
SELECT
    id,
    name
FROM users;
```
