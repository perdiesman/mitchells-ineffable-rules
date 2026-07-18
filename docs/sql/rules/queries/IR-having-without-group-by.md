# IR-having-without-group-by

Detect HAVING clauses used without a corresponding GROUP BY clause.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT count(*) FROM users HAVING count(*) > 5;
```

####  Correct Example
```sql
SELECT count(*) FROM users WHERE id > 0;
```

#### Additional Validations
```sql
SELECT role, count(*) FROM users GROUP BY role HAVING count(*) > 5;
```
