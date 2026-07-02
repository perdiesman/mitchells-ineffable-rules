# IR-is-null-space

Standardize spacing for null predicates (ISNULL -> IS NULL, ISNOTNULL -> IS NOT NULL).

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
SELECT * FROM users WHERE activeISNULL;
```

####  Correct Example #1
```sql
SELECT * FROM users WHERE active IS NULL;
```

#### ❌ Violating Example #2
```sql
SELECT * FROM users WHERE ageISNOTNULL;
```

####  Correct Example #2
```sql
SELECT * FROM users WHERE age IS NOT NULL;
```

#### Additional Validations
```sql
SELECT * FROM users WHERE age IS NULL;
```

```sql
SELECT * FROM users WHERE age IS NOT NULL;
```

```sql
SELECT 'isnull' AS str FROM users;
```
