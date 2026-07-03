# IR-null-coalesce

Standardize nullable equality predicates to COALESCE(x, -1) form.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
SELECT * FROM users WHERE active = -1 OR active IS NULL;
```

####  Correct Example #1
```sql
SELECT * FROM users WHERE COALESCE(active, -1) = -1;
```

#### ❌ Violating Example #2
```sql
SELECT * FROM t1 JOIN t2 ON t1.id = t2.id OR (t1.id IS NULL AND t2.id IS NULL);
```

####  Correct Example #2
```sql
SELECT * FROM t1 JOIN t2 ON COALESCE(t1.id, -1) = COALESCE(t2.id, -1);
```

#### Additional Validations
```sql
SELECT * FROM users WHERE COALESCE(active, -1) = -1;
```

```sql
SELECT * FROM t1 JOIN t2 ON COALESCE(t1.id, -1) = COALESCE(t2.id, -1);
```
