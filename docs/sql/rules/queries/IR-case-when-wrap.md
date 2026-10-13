# IR-case-when-wrap

Keep WHEN and THEN on one line when they fit; otherwise put THEN on an indented continuation line.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: No
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_line_length` (Default: `120`): Line length threshold for wrapping a WHEN/THEN arm. *Note: Value dynamically inherited from rule [`IR-line-length`](../general/IR-line-length.md) -> `max_length` if not configured.*

#### ❌ Violating Example
```sql
CASE
                WHEN a_very_long_condition_name = :condition_value AND another_long_condition_name = :other_value THEN calculate_a_very_long_result_name(:result_value)
    ELSE 0
END
```

####  Correct Example
```sql
CASE
    WHEN a_very_long_condition_name = :condition_value AND another_long_condition_name = :other_value
        THEN calculate_a_very_long_result_name(:result_value)
    ELSE 0
END
```

#### Additional Validations
```sql
CASE WHEN enabled THEN value ELSE 0 END
```

```sql
CASE
    WHEN enabled THEN value
    ELSE 0
END
```
