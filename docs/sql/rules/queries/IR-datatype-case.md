# IR-datatype-case

Standardize SQL data types to be uppercase.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT 1::text, '2026-07-11'::timestamp with time zone;
```

####  Correct Example
```sql
SELECT 1::TEXT, '2026-07-11'::TIMESTAMP WITH TIME ZONE;
```

#### Additional Validations
```sql
SELECT 1::INTEGER;
```
