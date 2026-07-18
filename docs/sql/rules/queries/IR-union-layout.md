# IR-union-layout

Enforce that set operators (UNION, UNION ALL, INTERSECT, EXCEPT) are on their own line, aligned with the query block.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT id FROM t1 UNION ALL SELECT id FROM t2;
```

####  Correct Example
```sql
SELECT id FROM t1
UNION ALL
SELECT id FROM t2;
```

#### Additional Validations
```sql
SELECT id FROM t1
UNION
SELECT id FROM t2;
```
