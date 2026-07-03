# IR-count-star

Standardize COUNT(1) or row-counting expressions to COUNT(*).

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT COUNT(1) FROM users;
```

####  Correct Example
```sql
SELECT COUNT(*) FROM users;
```
