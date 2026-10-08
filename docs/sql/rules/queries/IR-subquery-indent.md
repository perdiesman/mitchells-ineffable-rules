# IR-subquery-indent

Subqueries should be indented 4 spaces relative to their opening parenthesis.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: No
- **Trellis Safe**: Yes
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
SELECT * FROM (
SELECT a FROM t
) sub;
```

####  Correct Example #1
```sql
SELECT * FROM (
        SELECT a FROM t
    ) sub;
```

#### ❌ Violating Example #2
```sql
SELECT * FROM users WHERE id IN (
SELECT user_id FROM roles
);
```

####  Correct Example #2
```sql
SELECT * FROM users WHERE id IN (
    SELECT user_id FROM roles
);
```

#### ❌ Violating Example #3
```sql
UPDATE sample_item SET state_id = (SELECT state.id
FROM sample_state state
WHERE state.code = sample_item.state_code);
```

####  Correct Example #3
```sql
UPDATE sample_item SET state_id = (
    SELECT state.id
    FROM sample_state state
    WHERE state.code = sample_item.state_code
);
```

#### ❌ Violating Example #4
```sql
SELECT parent.item_id
FROM
    sample_parent parent
    LEFT JOIN LATERAL (
        SELECT child.parent_id
        FROM sample_child child
    ) child ON true;
```

####  Correct Example #4
```sql
SELECT parent.item_id
FROM
    sample_parent parent
    LEFT JOIN LATERAL (
            SELECT child.parent_id
            FROM sample_child child
        ) child ON true;
```

#### Additional Validations
```sql
SELECT * FROM (/* preserve placement */ SELECT item_id FROM sample_item
) sample_rows;
```
