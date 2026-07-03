# IR-join-and

Split AND conditions in JOIN ON clauses to separate lines, indented 4 spaces.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT * FROM t1 JOIN t2 ON t1.id = t2.id AND t1.active = t2.active;
```

####  Correct Example
```sql
SELECT * FROM t1 JOIN t2 ON t1.id = t2.id
    AND t1.active = t2.active;
```

#### Additional Validations
```sql
SELECT * FROM t1 JOIN t2 ON t1.id = t2.id;
```
