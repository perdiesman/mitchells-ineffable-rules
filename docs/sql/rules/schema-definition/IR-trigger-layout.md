# IR-trigger-layout

Format and wrap long CREATE TRIGGER statements to standard multiline layout.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Schema Definition Rules
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum line length before wrapping trigger statements.

#### ❌ Violating Example
```sql
CREATE TRIGGER update_user_access BEFORE UPDATE OF manager ON my_schema.my_table FOR EACH ROW EXECUTE FUNCTION my_schema.my_function();
```

####  Correct Example
```sql
CREATE TRIGGER update_user_access
    BEFORE UPDATE OF manager ON my_schema.my_table
    FOR EACH ROW
    EXECUTE FUNCTION my_schema.my_function();
```

#### Additional Validations
```sql
CREATE TRIGGER short_trigger BEFORE INSERT ON t FOR EACH ROW EXECUTE FUNCTION f();
```
