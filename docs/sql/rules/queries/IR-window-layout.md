# IR-window-layout

Long or multiline window expressions should indent OVER clauses, place each PARTITION BY field on its own line, and align wrapper arguments.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: No
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum line length before expanding a window expression. *Note: Value dynamically inherited from rule [`IR-line-length`](../general/IR-line-length.md) -> `max_length` if not configured.*

#### ❌ Violating Example
```sql
    coalesce(lag(item_count) OVER (
        PARTITION BY item_type, item_region
        ORDER BY recorded_at ASC
    ), 0) AS prior_count
```

####  Correct Example
```sql
    coalesce(
        lag(item_count) OVER (
            PARTITION BY
                item_type,
                item_region
            ORDER BY recorded_at ASC
        ),
        0
    ) AS prior_count
```

#### Additional Validations
```sql
SELECT lag(item_count) OVER (ORDER BY recorded_at) FROM sample_item;
```
