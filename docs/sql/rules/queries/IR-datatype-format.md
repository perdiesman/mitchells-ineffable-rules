# IR-datatype-format

Standardize SQL data types to use their long format (character varying instead of varchar, timestamp with time zone instead of timestamptz).

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT 1::varchar, '2026-07-11'::timestamptz;
```

####  Correct Example
```sql
SELECT 1::character varying, '2026-07-11'::timestamp with time zone;
```

#### Additional Validations
```sql
SELECT 1::character varying(255);
```
