# IR-trailing-semicolon

Place semicolons immediately after statement text and require a final semicolon only in multi-statement files.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Commit Profile**: No
- **MyBatis Safe**: No
- **Trellis Safe**: No
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT * FROM users
    ;
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
SELECT * FROM users
```
