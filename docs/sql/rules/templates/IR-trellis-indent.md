# IR-trellis-indent

Indent SQL inside directive-controlled multiline parentheses one level without moving Trellis comments.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Template Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: No
- **Trellis Safe**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `indent_size` (Default: `4`): Spaces added inside a multiline parenthesized expression. *Note: Value dynamically inherited from rule [`IR-indent`](../general/IR-indent.md) -> `indent_size` if not configured.*

#### Executable Cases
##### directive-controlled collection — Fixed
```sql
WHERE
    item_id IN (
-- trellis: for item in item_ids separator=","
  :item
-- trellis: endfor
  )
```

Expected fixed output:
```sql
WHERE
    item_id IN (
-- trellis: for item in item_ids separator=","
        :item
-- trellis: endfor
    )
```

##### directive layout remains unchanged — Accepted
```sql
VALUES (
    -- trellis: if optional_value
    :optional_value
    -- trellis: endif
)
```
