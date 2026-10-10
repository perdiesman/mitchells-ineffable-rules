# IR-table-alias-as

Table, subquery, and table-function aliases should not use AS, except generate_series aliases, which should use AS.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: No
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

```sql
SELECT * FROM generate_series(1, 3) AS item_number;
```
