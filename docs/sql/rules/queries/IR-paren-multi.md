# IR-paren-multi

Parenthesized logical conditions stay inline when they fit; longer groups put each condition on its own indented line. Nested groups keep their own layout.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: No
- **Trellis Safe**: No
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT * FROM users WHERE active AND (
    enabled
    OR not blocked
);
```

####  Correct Example
```sql
SELECT * FROM users WHERE active AND (enabled OR not blocked);
```

#### Additional Validations
```sql
SELECT item_id FROM sample_item WHERE NOT EXISTS (SELECT 1 FROM sample_child);
```

```sql
SELECT item_id FROM sample_item WHERE (created_at BETWEEN :start AND :end);
```

```sql
SELECT a.id FROM a JOIN b ON (
    a.id = b.id
    OR (
        a.value IS NULL
        AND b.value IS NULL
    )
);
```
