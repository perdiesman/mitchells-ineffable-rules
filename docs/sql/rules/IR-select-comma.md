# IR-select-comma

Missing commas between SELECT columns split across lines should be inserted.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT
    id
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

#### Additional Validations
```sql
SELECT id AS user_id FROM users;
```
