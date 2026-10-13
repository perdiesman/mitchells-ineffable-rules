# IR-set-multi

Put each assignment in a multiline SET clause on its own indented line.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Data Modification Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: No
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `indent_size` (Default: `4`): Spaces used to indent SET assignments. *Note: Value dynamically inherited from rule [`IR-indent`](../general/IR-indent.md) -> `indent_size` if not configured.*

#### ❌ Violating Example
```sql
SET first_value = excluded.first_value,
    second_value = excluded.second_value
```

####  Correct Example
```sql
SET
    first_value = excluded.first_value,
    second_value = excluded.second_value
```

#### Additional Validations
```sql
SET work_mem TO '128MB';
```
