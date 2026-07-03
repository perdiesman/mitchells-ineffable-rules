# IR-distinct-parentheses

Remove redundant parentheses around DISTINCT arguments, preserving DISTINCT ON (col) syntax.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT DISTINCT(id), name FROM users;
```

####  Correct Example
```sql
SELECT DISTINCT id, name FROM users;
```

#### Additional Validations
```sql
SELECT DISTINCT ON (company_id) id, name FROM users;
```
