# IR-like-no-wildcard

Simplify LIKE comparisons to standard = comparisons when the pattern contains no wildcard characters (% or _).

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT * FROM users WHERE name LIKE 'Alice';
```

####  Correct Example
```sql
SELECT * FROM users WHERE name = 'Alice';
```

#### Additional Validations
```sql
SELECT * FROM users WHERE name LIKE 'A%';
```

```sql
SELECT * FROM users WHERE name LIKE 'A_c';
```

```sql
SELECT * FROM users WHERE name ILIKE 'Alice';
```
