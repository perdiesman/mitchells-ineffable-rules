# IR-where-multi

Each AND/OR clause in a multi-condition WHERE clause should start on its own line, indented at 4 spaces.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT id FROM users WHERE some_long_column_identifier_active = true AND another_long_column_identifier_type = 'admin' OR age_greater_than_limit > 21;
```

####  Correct Example
```sql
SELECT id FROM users WHERE
    some_long_column_identifier_active = true
    AND another_long_column_identifier_type = 'admin'
    OR age_greater_than_limit > 21;
```

#### Additional Validations
```sql
SELECT id FROM users WHERE active = true;
```
