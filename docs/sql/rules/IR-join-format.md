# IR-join-format

Standardize formatting of JOIN clauses: collapse split qualifiers (e.g., LEFT JOIN on same line) and align ON indentation.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT * FROM t1 LEFT
JOIN t2
ON t1.id = t2.id;
```

####  Correct Example
```sql
SELECT * FROM t1 LEFT JOIN t2
    ON t1.id = t2.id;
```

#### Additional Validations
```sql
SELECT * FROM t1 LEFT JOIN t2 ON t1.id = t2.id;
```
