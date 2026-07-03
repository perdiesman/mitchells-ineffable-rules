# IR-trailing-semicolon

Enforce that the last SQL statement ends with a trailing semicolon, placed immediately after the statement text.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
SELECT * FROM users
```

####  Correct Example #1
```sql
SELECT * FROM users;
```

#### ❌ Violating Example #2
```sql
SELECT * FROM users
    ;
```

####  Correct Example #2
```sql
SELECT * FROM users;
```

#### Additional Validations
```sql
SELECT * FROM users; -- comment at end
```
