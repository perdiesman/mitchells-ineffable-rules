# IR-as-spacing

The AS keyword must be preceded by exactly one space.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_line_length` (Default: `120`): Line length threshold for recombining an alias line. *Note: Value dynamically inherited from rule [`IR-line-length`](../general/IR-line-length.md) -> `max_length` if not configured.*

#### ❌ Violating Example
```sql
SELECT a   AS b FROM t;
```

####  Correct Example
```sql
SELECT a AS b FROM t;
```

#### Additional Validations
```sql
SELECT a AS b FROM t;
```

```sql
SELECT a_very_long_expression_name_that_should_remain_on_its_own_line
AS a_very_long_alias_name_that_would_exceed_the_configured_line_limit FROM t;
```
