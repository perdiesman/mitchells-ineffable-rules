# IR-table-alias-as

Table and subquery aliases should not use the AS keyword.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
SELECT * FROM users AS u LEFT JOIN roles AS r ON u.role_id = r.id;
```

####  Correct Example #1
```sql
SELECT * FROM users u LEFT JOIN roles r ON u.role_id = r.id;
```

#### ❌ Violating Example #2
```sql
SELECT * FROM (SELECT * FROM raw_users) AS sub;
```

####  Correct Example #2
```sql
SELECT * FROM (SELECT * FROM raw_users) sub;
```

#### Additional Validations
```sql
SELECT * FROM users u;
```

```sql
SELECT * FROM (SELECT a AS b FROM t) sub;
```
