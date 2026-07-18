# IR-select-wildcard

Avoid wildcard SELECT * in query headers and subqueries; explicitly list columns instead.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
SELECT * FROM users;
```

####  Correct Example #1
```sql
SELECT id, name, email FROM users;
```

#### ❌ Violating Example #2
```sql
SELECT u.* FROM users u;
```

####  Correct Example #2
```sql
SELECT u.id, u.name FROM users u;
```

#### Additional Validations
```sql
SELECT count(*) FROM users;
```

```sql
SELECT count(1) FROM users;
```

```sql
SELECT id, name FROM users WHERE id IN (SELECT user_id FROM profiles);
```
