# IR-where-multi

Keep a multi-condition WHERE clause inline when it fits; otherwise put each condition on its own indented line.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: No
- **Trellis Safe**: Yes
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

```sql
SELECT id FROM users WHERE active = true AND retired = false;
```
