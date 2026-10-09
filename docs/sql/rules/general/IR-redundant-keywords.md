# IR-redundant-keywords

Remove redundant implied keywords like INNER, OUTER, and non-window ASC.

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
