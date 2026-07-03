# IR-is-null

Standardize NULL comparison predicates to use IS NULL and IS NOT NULL operators.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT * FROM users WHERE deleted_at = NULL OR updated_at != NULL;
```

####  Correct Example
```sql
SELECT * FROM users WHERE deleted_at IS NULL OR updated_at IS NOT NULL;
```
