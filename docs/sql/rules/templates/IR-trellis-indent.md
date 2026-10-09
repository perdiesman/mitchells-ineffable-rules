# IR-trellis-indent

Indent Trellis blocks like programming-language control flow and align multiline parentheses within those blocks.

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
##### conditional WHERE predicates — Fixed
```sql
WHERE TRUE
-- trellis: if enabled
AND active = TRUE
-- trellis: endif
```

Expected fixed output:
```sql
WHERE
    TRUE
    -- trellis: if enabled
        AND active = TRUE
    -- trellis: endif
```

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

##### directive layout aligns with its body — Fixed
```sql
VALUES (
-- trellis: if optional_value
    :optional_value
-- trellis: endif
)
```

Expected fixed output:
```sql
VALUES (
    -- trellis: if optional_value
        :optional_value
    -- trellis: endif
)
```

##### choose branches — Fixed
```sql
-- trellis: choose order
-- trellis: when "name"
ORDER BY item_name
-- trellis: otherwise
ORDER BY item_id
-- trellis: endchoose
```

Expected fixed output:
```sql
-- trellis: choose order
    -- trellis: when "name"
        ORDER BY item_name
    -- trellis: otherwise
        ORDER BY item_id
-- trellis: endchoose
```
