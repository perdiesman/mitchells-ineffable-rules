# IR-where-single

Single WHERE condition should be on the same line as the WHERE keyword.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT id FROM users
WHERE
    active = true;
```

####  Correct Example
```sql
SELECT id FROM users
WHERE active = true;
```

#### Additional Validations
```sql
SELECT id FROM users WHERE active = true;
```

```sql
SELECT id FROM users WHERE active = true AND age > 21;
```
