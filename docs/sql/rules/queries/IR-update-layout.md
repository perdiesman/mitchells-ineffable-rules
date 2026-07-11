# IR-update-layout

Format and wrap long UPDATE statements: align SET and WHERE with UPDATE, indent assignments.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum line length before wrapping UPDATE statements.

#### ❌ Violating Example
```sql
UPDATE dashboard.layout SET default_layout = false WHERE user_id = NEW.user_id AND type_id = NEW.type_id AND id != NEW.id;
```

####  Correct Example
```sql
UPDATE dashboard.layout
SET
    default_layout = false
WHERE user_id = NEW.user_id AND type_id = NEW.type_id AND id != NEW.id;
```

#### Additional Validations
```sql
UPDATE t SET a = 1 WHERE b = 2;
```
