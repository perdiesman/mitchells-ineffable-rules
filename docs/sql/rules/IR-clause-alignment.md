# IR-clause-alignment

Main query clause keywords (SELECT, FROM, WHERE, GROUP BY, HAVING, ORDER BY, LIMIT) must have the exact same indentation within the same query block when the query spans multiple lines.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
SELECT id, name
  FROM users
  WHERE active = true;
```

####  Correct Example #1
```sql
SELECT id, name
FROM users
WHERE active = true;
```

#### ❌ Violating Example #2
```sql
SELECT id
FROM users
WHERE id IN (
    SELECT user_id
      FROM roles
    WHERE role_name = 'admin'
);
```

####  Correct Example #2
```sql
SELECT id
FROM users
WHERE id IN (
    SELECT user_id
    FROM roles
    WHERE role_name = 'admin'
);
```

#### Additional Validations
```sql
SELECT id, name FROM users WHERE active = true;
```
