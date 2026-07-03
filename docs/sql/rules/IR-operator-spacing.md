# IR-operator-spacing

Operators should have a single space on both sides.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT a+b AS c FROM users WHERE id=1;
```

####  Correct Example
```sql
SELECT a + b AS c FROM users WHERE id = 1;
```

#### Additional Validations
```sql
SELECT -5 FROM users;
```

```sql
SELECT COUNT(*) FROM users;
```
