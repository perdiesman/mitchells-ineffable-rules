# IR-truncate-table

Prefer TRUNCATE table_name over DELETE FROM table_name with no conditions.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: Data Modification Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
DELETE FROM users;
```

####  Correct Example
```sql
TRUNCATE users;
```

#### Additional Validations
```sql
DELETE FROM users WHERE id = 1;
```

```sql
DELETE FROM users USING logs WHERE logs.user_id = users.id;
```
