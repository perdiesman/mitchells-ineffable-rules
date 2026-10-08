# IR-clause-alignment

Main query clause keywords (SELECT, FROM, WHERE, GROUP BY, HAVING, ORDER BY, LIMIT) must have the exact same indentation within the same query block when the query spans multiple lines.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: No
- **MyBatis Safe**: Yes
- **Trellis Safe**: No
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
SELECT id, name FROM users
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

```sql
SELECT item_id
FROM sample_item
WHERE parent_id IS NOT DISTINCT FROM :parent_id;
```
