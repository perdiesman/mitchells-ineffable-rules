# IR-trailing-semicolon

Enforce that the last SQL statement ends with a trailing semicolon.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT * FROM users
```

####  Correct Example
```sql
SELECT * FROM users;
```

#### Additional Validations
```sql
SELECT * FROM users; -- comment at end
```

```sql
SELECT * FROM users;  
```
