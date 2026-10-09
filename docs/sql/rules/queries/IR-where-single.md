# IR-where-single

Keep a single WHERE condition inline when it fits; otherwise place the condition on the next indented line.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: No
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_line_length` (Default: `120`): Maximum length for an inline WHERE clause. *Note: Value dynamically inherited from rule [`IR-line-length`](../general/IR-line-length.md) -> `max_length` if not configured.*
  - `indent_size` (Default: `4`): Spaces used for a wrapped WHERE condition. *Note: Value dynamically inherited from rule [`IR-indent`](../general/IR-indent.md) -> `indent_size` if not configured.*

#### ❌ Violating Example #1
```sql
SELECT id FROM users
WHERE
    active = true;
```

####  Correct Example #1
```sql
SELECT id FROM users
WHERE active = true;
```

#### ❌ Violating Example #2
```sql
SELECT item_id FROM sample_item WHERE recorded_timestamp_for_requested_interval BETWEEN timezone('utc', :requested_interval_start) AND timezone('utc', :requested_interval_end);
```

####  Correct Example #2
```sql
SELECT item_id FROM sample_item WHERE
    recorded_timestamp_for_requested_interval BETWEEN timezone('utc', :requested_interval_start) AND timezone('utc', :requested_interval_end);
```

#### Additional Validations
```sql
SELECT id FROM users WHERE active = true;
```

```sql
SELECT id FROM users WHERE active = true AND age > 21;
```

```sql
SELECT id FROM users WHERE created_at BETWEEN :start AND :end;
```
