# IR-indent

Indent should be equal amounts of spaces (default 4).

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Default Configuration**:
  - `enabled`: `true`
  - `indent_size`: `4`

#### ❌ Violating Example
```sql
SELECT
  id,
   name
FROM users;
```

####  Correct Example
```sql
SELECT
    id,
    name
FROM users;
```
