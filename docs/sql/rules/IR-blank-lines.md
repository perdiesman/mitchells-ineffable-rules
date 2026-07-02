# IR-blank-lines

Limit consecutive blank lines to a maximum of one.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT * FROM users;



SELECT * FROM roles;
```

####  Correct Example
```sql
SELECT * FROM users;

SELECT * FROM roles;
```

#### Additional Validations
```sql
SELECT * FROM users;

SELECT * FROM roles;
```
