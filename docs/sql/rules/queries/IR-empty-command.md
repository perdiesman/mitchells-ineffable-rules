# IR-empty-command

Remove empty SQL commands, such as duplicate semicolons or leading semicolons.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: No
- **MyBatis Safe**: Yes
- **Trellis Safe**: No
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
