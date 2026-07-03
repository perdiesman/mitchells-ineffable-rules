# IR-paren-single

Unnecessary parentheses around a single condition should be removed.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
SELECT id FROM users WHERE (active = true);
```

####  Correct Example #1
```sql
SELECT id FROM users WHERE active = true;
```

#### ❌ Violating Example #2
```sql
SELECT (id)::integer FROM users;
```

####  Correct Example #2
```sql
SELECT id::integer FROM users;
```

#### Additional Validations
```sql
SELECT (a + b)::integer FROM users;
```

```sql
SELECT COALESCE(id, 0) FROM users;
```

```sql
SELECT id FROM users WHERE (active = true AND type = 'admin');
```
