# IR-between

Standardize range predicate check of form 'a >= b AND a <= c' to 'a BETWEEN b AND c'.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
SELECT * FROM users WHERE age >= 18 AND age <= 65;
```

####  Correct Example #1
```sql
SELECT * FROM users WHERE age BETWEEN 18 AND 65;
```

#### ❌ Violating Example #2
```sql
SELECT * FROM users WHERE age <= 65 AND age >= 18;
```

####  Correct Example #2
```sql
SELECT * FROM users WHERE age BETWEEN 18 AND 65;
```
