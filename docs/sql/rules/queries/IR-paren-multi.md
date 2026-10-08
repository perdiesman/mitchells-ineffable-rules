# IR-paren-multi

Parentheses wrapping multiple logical conditions in WHERE/ON clauses must format contents on separate lines, indented 4 spaces.

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
SELECT * FROM users WHERE active AND (enabled OR not blocked);
```

####  Correct Example
```sql
SELECT * FROM users WHERE active AND (
    enabled
    OR not blocked
);
```

#### Additional Validations
```sql
SELECT item_id FROM sample_item WHERE NOT EXISTS (SELECT 1 FROM sample_child);
```
