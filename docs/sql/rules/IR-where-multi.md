# IR-where-multi

Each AND/OR clause in a multi-condition WHERE clause should start on its own line, indented at 4 spaces.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT id FROM users WHERE active = true AND type = 'admin' OR age > 21;
```

####  Correct Example
```sql
SELECT id FROM users WHERE
    active = true
    AND type = 'admin'
    OR age > 21;
```

#### Additional Validations
```sql
SELECT id FROM users WHERE active = true;
```
