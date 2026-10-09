# IR-where-multi

Keep a multi-condition WHERE clause inline when it fits; otherwise put each condition on its own indented line.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: Yes
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
SELECT id FROM users WHERE some_long_column_identifier_active = true AND another_long_column_identifier_type = 'admin' OR age_greater_than_limit > 21;
```

####  Correct Example #1
```sql
SELECT id FROM users WHERE
    some_long_column_identifier_active = true
    AND another_long_column_identifier_type = 'admin'
    OR age_greater_than_limit > 21;
```

#### ❌ Violating Example #2
```sql
SELECT item_id FROM sample_item WHERE recorded_at BETWEEN :start
    AND :end AND owning_organization_identifier = :owning_organization_identifier AND processing_status = :processing_status;
```

####  Correct Example #2
```sql
SELECT item_id FROM sample_item WHERE
    recorded_at BETWEEN :start AND :end
    AND owning_organization_identifier = :owning_organization_identifier
    AND processing_status = :processing_status;
```

#### Additional Validations
```sql
SELECT id FROM users WHERE active = true;
```

```sql
SELECT id FROM users WHERE active = true AND retired = false;
```

```sql
SELECT id FROM users WHERE created_at BETWEEN :start AND :end;
```
