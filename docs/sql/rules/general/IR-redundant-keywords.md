# IR-redundant-keywords

Remove redundant implied keywords like INNER, LEFT/RIGHT OUTER, and non-window ASC while retaining explicit FULL OUTER JOIN.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Commit Profile**: Yes
- **Intentional Semantic Rewrite**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: No
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT * FROM t1 INNER JOIN t2 LEFT OUTER JOIN t3 ORDER BY col ASC;
```

####  Correct Example
```sql
SELECT * FROM t1 JOIN t2 LEFT JOIN t3 ORDER BY col;
```

#### Additional Validations
```sql
SELECT * FROM first_item FULL OUTER JOIN second_item USING (item_id);
```
