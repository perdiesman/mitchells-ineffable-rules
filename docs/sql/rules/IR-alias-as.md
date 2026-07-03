# IR-alias-as

Column aliases must use the AS keyword.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT id user_id, name customer_name FROM users;
```

####  Correct Example
```sql
SELECT id AS user_id, name AS customer_name FROM users;
```

#### Additional Validations
```sql
SELECT id AS user_id FROM users;
```

```sql
SELECT COUNT(*) AS cnt FROM users;
```
