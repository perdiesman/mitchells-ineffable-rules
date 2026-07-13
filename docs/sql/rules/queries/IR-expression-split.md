# IR-expression-split

Long lines should split on function/expression parentheses, and optionally on additive/logical operators if still too long.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_line_length` (Default: `100`): Line length threshold above which long expressions will be split.

#### ❌ Violating Example #1
```sql
SELECT (date_trunc('hour', start_time) + date_part('minutes', start_time)::int / 15 * '15 Minutes'::interval) AS start_time;
```

####  Correct Example #1
```sql
SELECT
(
    date_trunc('hour', start_time)
    + date_part('minutes', start_time)::int
    / 15
    * '15 Minutes'::interval
) AS start_time;
```

#### ❌ Violating Example #2
```sql
SELECT min(date_trunc('hour', start_time) + date_part('minutes', start_time)::int / 15 * '15 Minutes'::interval) AS start_time;
```

####  Correct Example #2
```sql
SELECT min(
        date_trunc('hour', start_time)
        + date_part('minutes', start_time)::int
        / 15
        * '15 Minutes'::interval
    ) AS start_time;
```

#### ❌ Violating Example #3
```sql
INSERT INTO t (c) VALUES (1), (2);
```

####  Correct Example #3
```sql
INSERT INTO t (c) VALUES
    (1),
    (2);
```

#### Additional Validations
```sql
SELECT min(id) FROM users;
```

```sql
SELECT (id) FROM users;
```

```sql
INSERT INTO t (c) VALUES (1);
```

```sql
INSERT INTO t (c) VALUES
    (1),
    (2);
```
