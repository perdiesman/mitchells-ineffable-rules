# IR-case-when-wrap

Keep WHEN and THEN on one line when they fit; otherwise put THEN on an indented continuation line.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: No
- **Configuration Options**:
  - `enabled`: `true`

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
    WHEN enabled
        THEN value
    ELSE 0
END
```
