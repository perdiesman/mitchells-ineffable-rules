# IR-join-parens

Unnecessary parentheses around a JOIN clause should be removed.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT * FROM (t1 LEFT JOIN t2 ON t1.id = t2.id);
```

####  Correct Example
```sql
SELECT * FROM t1 LEFT JOIN t2 ON t1.id = t2.id;
```

#### Additional Validations
```sql
SELECT * FROM (SELECT * FROM t1) AS sub LEFT JOIN t2 ON sub.id = t2.id;
```
