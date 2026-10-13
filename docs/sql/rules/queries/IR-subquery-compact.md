# IR-subquery-compact

Multiline subquery sources inside FROM or JOIN clauses should be compacted to a single line if they fit within 140 characters.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: No
- **MyBatis Safe**: No
- **Trellis Safe**: No
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT * FROM (
    SELECT a FROM t
) sub;
```

####  Correct Example
```sql
SELECT * FROM (SELECT a FROM t) sub;
```

#### Additional Validations
```sql
SELECT * FROM (
    SELECT a FROM t -- keep comments
) sub;
```
