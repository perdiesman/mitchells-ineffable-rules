# IR-keyword-case

SQL keywords must be in uppercase.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
select id, username from users where active = true;
```

####  Correct Example
```sql
SELECT id, username FROM users WHERE active = true;
```
