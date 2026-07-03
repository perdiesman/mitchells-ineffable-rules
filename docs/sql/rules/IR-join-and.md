# IR-join-and

Split AND or OR conditions in JOIN ON clauses to separate lines, indented 4 spaces.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
SELECT * FROM t1 JOIN t2 ON t1.id = t2.id AND t1.active = t2.active;
```

####  Correct Example #1
```sql
SELECT * FROM t1 JOIN t2 ON t1.id = t2.id
    AND t1.active = t2.active;
```

#### ❌ Violating Example #2
```sql
SELECT * FROM t1 JOIN t2 ON t1.id = t2.id OR t1.code = t2.code;
```

####  Correct Example #2
```sql
SELECT * FROM t1 JOIN t2 ON t1.id = t2.id
    OR t1.code = t2.code;
```

#### Additional Validations
```sql
SELECT * FROM t1 JOIN t2 ON t1.id = t2.id;
```
