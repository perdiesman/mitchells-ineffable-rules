# IR-coalesce-standard

Use standard COALESCE instead of dialect-specific null-handling functions like NVL, IFNULL, or ISNULL.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
SELECT NVL(val, 0) FROM users;
```

####  Correct Example #1
```sql
SELECT COALESCE(val, 0) FROM users;
```

#### ❌ Violating Example #2
```sql
SELECT IFNULL(val, 0) FROM users;
```

####  Correct Example #2
```sql
SELECT COALESCE(val, 0) FROM users;
```

#### ❌ Violating Example #3
```sql
SELECT ISNULL(val, 0) FROM users;
```

####  Correct Example #3
```sql
SELECT COALESCE(val, 0) FROM users;
```

#### Additional Validations
```sql
SELECT COALESCE(val, 0) FROM users;
```
