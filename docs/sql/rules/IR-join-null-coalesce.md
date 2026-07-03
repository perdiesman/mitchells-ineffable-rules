# IR-join-null-coalesce

Standardize predicate checks of form 'x = v OR x IS NULL' to COALESCE(x, -1) = v.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
SELECT * FROM users WHERE active = true OR active IS NULL;
```

####  Correct Example #1
```sql
SELECT * FROM users WHERE COALESCE(active, -1) = true;
```

#### ❌ Violating Example #2
```sql
SELECT * FROM users WHERE active IS NULL OR active = true;
```

####  Correct Example #2
```sql
SELECT * FROM users WHERE COALESCE(active, -1) = true;
```
