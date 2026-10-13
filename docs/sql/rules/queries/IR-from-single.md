# IR-from-single

Single FROM entries should be on the same line as FROM; DELETE, FROM, and its target should share one line.

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
SELECT id
FROM
    users;
```

####  Correct Example #1
```sql
SELECT id
FROM users;
```

#### ❌ Violating Example #2
```sql
DELETE
FROM users
WHERE user_id = :user_id;
```

####  Correct Example #2
```sql
DELETE FROM users
WHERE user_id = :user_id;
```

#### Additional Validations
```sql
SELECT id
FROM (SELECT * FROM raw_users) AS sub;
```
