# IR-case-when-when

Remove duplicate adjacent WHEN keywords.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT CASE WHEN WHEN active = true THEN 1 ELSE 0 END FROM users;
```

####  Correct Example
```sql
SELECT CASE WHEN active = true THEN 1 ELSE 0 END FROM users;
```

#### Additional Validations
```sql
SELECT CASE WHEN active = true THEN 1 ELSE 0 END FROM users;
```
