# IR-parenthesized-expression-wrap

Long parenthesized arithmetic expressions should put each operand on an aligned continuation line and expand complex denominator calls.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: No
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_line_length` (Default: `120`): Line length threshold for expanding the expression. *Note: Value dynamically inherited from rule [`IR-line-length`](../general/IR-line-length.md) -> `max_length` if not configured.*

#### ❌ Violating Example
```sql
                (coalesce(max(current_outage), 0)::NUMERIC / greatest(coalesce(sum(normal_value * county_percent), 1)::INTEGER, 1)) - 1 AS outage_count
```

####  Correct Example
```sql
                (
                    coalesce(max(current_outage), 0)::NUMERIC
                    / greatest(
                        coalesce(
                            sum(normal_value * county_percent),
                            1
                        )::INTEGER,
                        1
                    )
                ) - 1 AS outage_count
```

#### Additional Validations
```sql
SELECT (current_count / expected_count) AS ratio;
```

```sql
SELECT (current_count + expected_count) AS total;
```
