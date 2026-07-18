# IR-raise-layout

Format and wrap long RAISE statements onto multiple lines.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Routine & Procedure Rules
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum line length before wrapping RAISE statements.

#### ❌ Violating Example
```sql
RAISE unique_violation USING MESSAGE = 'id: ' || NEW.id::text || ' already exists in my_schema.my_very_long_table_name_to_exceed_the_line_length_limit';
```

####  Correct Example
```sql
RAISE unique_violation
    USING MESSAGE = 'id: '
        || NEW.id::text
        || ' already exists in my_schema.my_very_long_table_name_to_exceed_the_line_length_limit';
```

#### Additional Validations
```sql
RAISE NOTICE 'short';
```
