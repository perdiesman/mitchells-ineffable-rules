# IR-raise-layout

Format and wrap long RAISE statements onto multiple lines.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum line length before wrapping RAISE statements.

#### ❌ Violating Example
```sql
RAISE unique_violation USING MESSAGE = 'id: ' || NEW.id::text || ' already exists in outage_data.coverage_geometry_bypass_table_and_other_fields';
```

####  Correct Example
```sql
RAISE unique_violation
    USING MESSAGE = 'id: '
        || NEW.id::text
        || ' already exists in outage_data.coverage_geometry_bypass_table_and_other_fields';
```

#### Additional Validations
```sql
RAISE NOTICE 'short';
```
