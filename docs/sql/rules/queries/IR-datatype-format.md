# IR-datatype-format

Standardize PostgreSQL data type aliases to their canonical long forms.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: Yes
- **Intentional Semantic Rewrite**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: No
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT 1::varchar, '2026-07-11'::timestamptz, 1::int;
```

####  Correct Example
```sql
SELECT 1::character varying, '2026-07-11'::timestamp with time zone, 1::integer;
```

#### Additional Validations
```sql
SELECT 1::character varying(255);
```
