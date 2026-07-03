# IR-from-multi

Multi-table or JOINed FROM entries should be formatted with one entry per line, indented at 4 spaces.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
SELECT * FROM t1, t2, t3 WHERE x = 1;
```

####  Correct Example #1
```sql
SELECT * FROM
    t1,
    t2,
    t3 WHERE x = 1;
```

#### ❌ Violating Example #2
```sql
SELECT * FROM t1 LEFT JOIN t2 ON t1.id = t2.id;
```

####  Correct Example #2
```sql
SELECT * FROM
    t1
    LEFT JOIN t2 ON t1.id = t2.id;
```

#### Additional Validations
```sql
SELECT * FROM t1;
```
