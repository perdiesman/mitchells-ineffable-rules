# IR-update-layout

Format and wrap long UPDATE statements: align SET and WHERE with UPDATE, indent assignments.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum line length before wrapping UPDATE statements.

#### ❌ Violating Example #1
```sql
UPDATE dashboard.layout SET default_layout = false WHERE user_id = NEW.user_id AND type_id = NEW.type_id AND id != NEW.id;
```

####  Correct Example #1
```sql
UPDATE dashboard.layout
SET default_layout = false
WHERE user_id = NEW.user_id AND type_id = NEW.type_id AND id != NEW.id;
```

#### ❌ Violating Example #2
```sql
UPDATE my_very_long_table SET my_first_very_long_field_with_very_long_value = 1, my_second_very_long_field_with_very_long_value = 2 WHERE some_condition;
```

####  Correct Example #2
```sql
UPDATE my_very_long_table
SET
    my_first_very_long_field_with_very_long_value = 1,
    my_second_very_long_field_with_very_long_value = 2
WHERE some_condition;
```

#### Additional Validations
```sql
UPDATE t SET a = 1 WHERE b = 2;
```
