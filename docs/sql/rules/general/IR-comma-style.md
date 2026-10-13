# IR-comma-style

Enforce trailing commas in multiline listings and forbid whitespace before commas.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: No
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
SELECT id
    , name
FROM users;
```

####  Correct Example #1
```sql
SELECT id,
     name
FROM users;
```

#### ❌ Violating Example #2
```sql
SELECT coalesce(item_count , 0) FROM users;
```

####  Correct Example #2
```sql
SELECT coalesce(item_count, 0) FROM users;
```

#### Additional Validations
```sql
SELECT id, name FROM users;
```
