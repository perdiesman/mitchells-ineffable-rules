# IR-table-function-indent

Keep a fitting table-function opener with its function name; otherwise indent multiline arguments as table continuations, with joined functions and their wrapped predicate expressions nested beneath the JOIN.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `indent_size` (Default: `4`): Spaces added inside a multiline table-function call. *Note: Value dynamically inherited from rule [`IR-indent`](../general/IR-indent.md) -> `indent_size` if not configured.*

#### Executable Cases
##### multiline FROM table function — Fixed
```sql
FROM sample.items_for_period(
        :period
    ) AS item
```

Expected fixed output:
```sql
FROM sample.items_for_period(
    :period
) AS item
```

##### short multiline table function — Fixed
```sql
FROM generate_series
    (:period_start, :period_end, '15 MINUTES' :: interval) AS period
```

Expected fixed output:
```sql
FROM generate_series(:period_start, :period_end, '15 MINUTES'::interval) AS period
```

##### multiline JOIN table function — Fixed
```sql
    JOIN sample.items_for_period(
        :period
    ) AS item ON TRUE
```

Expected fixed output:
```sql
    JOIN sample.items_for_period(
            :period
        ) AS item ON TRUE
```

##### joined table function with additive predicate continuation — Fixed
```sql
    JOIN sample.items_for_period(
        :period
    ) AS item ON event_time BETWEEN item.start_time AND item.start_time
+ item.duration
```

Expected fixed output:
```sql
    JOIN sample.items_for_period(
            :period
        ) AS item ON event_time BETWEEN item.start_time AND item.start_time
        + item.duration
```
