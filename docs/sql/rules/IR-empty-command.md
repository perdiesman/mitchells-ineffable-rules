# IR-empty-command

Remove empty SQL commands, such as duplicate semicolons or leading semicolons.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
;
SELECT id FROM users;;
```

####  Correct Example
```sql
SELECT id FROM users;
```

#### Additional Validations
```sql
SELECT 'a;b' FROM users;
```

```sql
SELECT id FROM users;
```
