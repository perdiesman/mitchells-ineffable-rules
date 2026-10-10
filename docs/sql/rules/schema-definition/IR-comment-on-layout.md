# IR-comment-on-layout

Overlong COMMENT ON statements place IS and the unchanged comment literal on an indented continuation line.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Schema Definition Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum line length before wrapping COMMENT ON. *Note: Value dynamically inherited from rule [`IR-line-length`](../general/IR-line-length.md) -> `max_length` if not configured.*
  - `indent_size` (Default: `4`): Continuation indentation in spaces. *Note: Value dynamically inherited from rule [`IR-indent`](../general/IR-indent.md) -> `indent_size` if not configured.*

#### ❌ Violating Example
```sql
COMMENT ON COLUMN sample_item.extraordinarily_long_status_name IS 'Status assigned after the item has completed validation and review.';
```

####  Correct Example
```sql
COMMENT ON COLUMN sample_item.extraordinarily_long_status_name
    IS 'Status assigned after the item has completed validation and review.';
```

#### Additional Validations
```sql
COMMENT ON TABLE sample_item IS 'Items.';
```
