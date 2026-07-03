# IR-comment-spacing

Enforce a single space after the double-dash comment prefix.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
--todo: clean up old table
SELECT * FROM users;
```

####  Correct Example
```sql
-- todo: clean up old table
SELECT * FROM users;
```

#### Additional Validations
```sql
-- already spaced comment
```

```sql
--- divider comment line
```

```sql
SELECT * FROM users; -- inline comment
```
