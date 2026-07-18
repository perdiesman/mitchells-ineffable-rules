# IR-self-comparison

Detect redundant self-comparisons where a column/identifier is compared to itself (e.g. x = x).

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
SELECT * FROM users WHERE age = age;
```

####  Correct Example #1
```sql
SELECT * FROM users WHERE age = 21;
```

#### ❌ Violating Example #2
```sql
SELECT * FROM users u WHERE u.id = u.id;
```

####  Correct Example #2
```sql
SELECT * FROM users u WHERE u.id = 100;
```

#### Additional Validations
```sql
SELECT * FROM users WHERE 1 = 1;
```

```sql
SELECT * FROM users WHERE true = true;
```

```sql
SELECT * FROM users u JOIN profiles p ON u.id = p.user_id;
```
