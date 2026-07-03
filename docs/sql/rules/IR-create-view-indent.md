# IR-create-view-indent

SELECT statements under a CREATE VIEW should be indented 4 spaces relative to the CREATE VIEW statement.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
CREATE VIEW v AS
SELECT * FROM users;
```

####  Correct Example
```sql
CREATE VIEW v AS
    SELECT * FROM users;
```

#### Additional Validations
```sql
CREATE MATERIALIZED VIEW mv AS
    SELECT * FROM users;
```
