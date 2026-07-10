# IR-subquery-depth-limit

Subquery nesting depth should not exceed the configured limit (default: 3). When over the limit, Common Table Expressions (CTEs) are preferred.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_depth` (Default: `3`): Maximum allowed subquery nesting depth.

#### ❌ Violating Example
```sql
SELECT * FROM (SELECT * FROM (SELECT * FROM (SELECT * FROM (SELECT * FROM users) u4) u3) u2) u1;
```

#### Additional Validations
```sql
SELECT * FROM (SELECT * FROM (SELECT * FROM (SELECT * FROM users) u3) u2) u1;
```

```sql
WITH u2 AS (SELECT * FROM users) SELECT * FROM u2;
```
