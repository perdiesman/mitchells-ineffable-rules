# IR-in-exists

EXISTS is preferred over IN with a subquery.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT * FROM users WHERE id IN (SELECT user_id FROM roles);
```

#### Additional Validations
```sql
SELECT * FROM users WHERE EXISTS (SELECT 1 FROM roles WHERE roles.user_id = users.id);
```
