# IR-paren-same-op

Unnecessary parentheses around homogeneous logical conditions should be removed.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT id FROM users WHERE (active = true AND type = 'admin' AND age > 21);
```

####  Correct Example
```sql
SELECT id FROM users WHERE active = true AND type = 'admin' AND age > 21;
```

#### Additional Validations
```sql
SELECT id FROM users WHERE (active = true AND type = 'admin') OR age > 21;
```

```sql
SELECT id FROM users WHERE active = true AND (type = 'admin' OR age > 21);
```

```sql
SELECT id FROM users WHERE (active = true);
```
