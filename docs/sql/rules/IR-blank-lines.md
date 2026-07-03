# IR-blank-lines

Limit consecutive blank lines to a configurable maximum.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_blank_lines` (Default: `1`): Maximum number of consecutive blank lines allowed.

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
