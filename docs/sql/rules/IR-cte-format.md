# IR-cte-format

Format layout of CTE WITH blocks: align subquery aliases, parenthesis and the final query block.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
WITH cte1 AS (SELECT * FROM t1), cte2 AS (SELECT * FROM t2) SELECT * FROM cte1;
```

####  Correct Example
```sql
WITH cte1 AS (
    SELECT * FROM t1
), cte2 AS (
    SELECT * FROM t2
)
SELECT * FROM cte1;
```

#### Additional Validations
```sql
WITH cte1 AS (
    SELECT * FROM t1
), cte2 AS (
    SELECT * FROM t2
)
SELECT * FROM cte1;
```
