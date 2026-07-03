# IR-from-single

Single FROM entry should be on the same line as the FROM keyword.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT id
FROM
    users;
```

####  Correct Example
```sql
SELECT id
FROM users;
```

#### Additional Validations
```sql
SELECT id
FROM (SELECT * FROM raw_users) AS sub;
```
