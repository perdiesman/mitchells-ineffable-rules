# IR-comma-style

Enforce trailing commas in multiline listings and forbid leading commas.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT id
    , name
FROM users;
```

####  Correct Example
```sql
SELECT id,
     name
FROM users;
```

#### Additional Validations
```sql
SELECT id, name FROM users;
```
