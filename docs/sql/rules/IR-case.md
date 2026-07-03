# IR-case

CASE statements should be formatted with WHEN/THEN on separate lines unless the entire block fits on a single line.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT CASE WHEN x = 1 THEN 'a' WHEN x = 2 THEN 'b' ELSE 'c' END FROM users;
```

####  Correct Example
```sql
SELECT 
    CASE
        WHEN x = 1 THEN 'a'
        WHEN x = 2 THEN 'b'
        ELSE 'c'
    END FROM users;
```

#### Additional Validations
```sql
SELECT CASE WHEN x = 1 THEN 'a' END FROM users;
```

```sql
SELECT 
    CASE
        WHEN x = 1 THEN 'a'
        ELSE 'b'
    END;
```
