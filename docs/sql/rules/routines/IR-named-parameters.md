# IR-named-parameters

Enforce named parameter notation (:= or =>) in function calls with 3 or more arguments.

- **Auto-Fixable**: No
- **Enabled by Default**: No
- **Category**: Routine & Procedure Rules
- **Configuration Options**:
  - `enabled`: `false`

#### Default `EXCLUDED_FUNCTIONS`
`ABS`, `AGE`, `ARRAY`, `ARRAY_APPEND`, `ARRAY_CAT`, `ARRAY_PREPEND`, `ARRAY_TO_STRING`, `AVG`, `CAST`, `CEIL`, `CLOCK_TIMESTAMP`, `COALESCE`, `CONCAT`, `COUNT`, `DATE_PART`, `DATE_TRUNC`, `DECODE`, `EXISTS`, `FLOOR`, `GETDATE`, `GREATEST`, `IFNULL`, `JSONB_BUILD_OBJECT`, `JSON_BUILD_OBJECT`, `LEAST`, `LOWER`, `MAX`, `MIN`, `NOW`, `NULLIF`, `NVL`, `REGEXP_MATCH`, `REGEXP_REPLACE`, `REGEXP_SPLIT_TO_ARRAY`, `REGEXP_SPLIT_TO_TABLE`, `REPLACE`, `ROUND`, `ROW_TO_JSON`, `SPLIT_PART`, `STATEMENT_TIMESTAMP`, `STRING_TO_ARRAY`, `SUBSTR`, `SUBSTRING`, `SUM`, `TO_JSON`, `TO_JSONB`, `TRANSACTION_TIMESTAMP`, `TRIM`, `UNNEST`, `UPPER`, `VALUES`

#### Default `RESERVED_WORDS`
`ALTER`, `AND`, `BEGIN`, `CASE`, `CREATE`, `DECLARE`, `DELETE`, `DROP`, `ELSE`, `END`, `FOR`, `FROM`, `IF`, `IN`, `INSERT`, `LOOP`, `NOT`, `ON`, `OR`, `RAISE`, `RETURN`, `SELECT`, `THEN`, `UPDATE`, `WHEN`, `WHERE`, `WHILE`, `WITH`

#### ❌ Violating Example
```sql
SELECT calculate_statistics(105, true, 'monthly_aggregation');
```

####  Correct Example
```sql
SELECT calculate_statistics(user_id := 105, include_deactivated := true, run_mode := 'monthly_aggregation');
```

#### Additional Validations
```sql
SELECT my_func(1, 2);
```

```sql
SELECT coalesce(a, b, c, d);
```

```sql
SELECT my_func(a := 1, b := 2, c := 3);
```
