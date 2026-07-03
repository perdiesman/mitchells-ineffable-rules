# IR-duplicate-content

Duplicate blocks of SQL of length >= 3 lines should be consolidated or simplified.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT a, b, c
FROM t1
WHERE x = 1;

SELECT a, b, c
FROM t1
WHERE x = 1;
```

#### Additional Validations
```sql
SELECT a, b, c
FROM t1
WHERE x = 1;

SELECT a, b, d
FROM t1
WHERE x = 1;
```
