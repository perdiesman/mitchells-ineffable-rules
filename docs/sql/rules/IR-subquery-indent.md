# IR-subquery-indent

Subqueries should be indented 4 spaces relative to their opening parenthesis.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
SELECT * FROM (
SELECT a FROM t
) sub;
```

####  Correct Example #1
```sql
SELECT * FROM (
        SELECT a FROM t
    ) sub;
```

#### ❌ Violating Example #2
```sql
SELECT * FROM users WHERE id IN (
SELECT user_id FROM roles
);
```

####  Correct Example #2
```sql
SELECT * FROM users WHERE id IN (
    SELECT user_id FROM roles
);
```
