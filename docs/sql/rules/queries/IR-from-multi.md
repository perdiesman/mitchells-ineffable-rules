# IR-from-multi

Multi-table or JOINed FROM entries should be formatted with one entry per line, indented at 4 spaces.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: Yes
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
SELECT * FROM t1, t2, t3 WHERE x = 1;
```

####  Correct Example #1
```sql
SELECT * FROM
    t1,
    t2,
    t3 WHERE x = 1;
```

#### ❌ Violating Example #2
```sql
SELECT * FROM t1 LEFT JOIN t2 ON t1.id = t2.id;
```

####  Correct Example #2
```sql
SELECT * FROM
    t1
    LEFT JOIN t2 ON t1.id = t2.id;
```

#### ❌ Violating Example #3
```sql
SELECT * FROM first_table FULL
    OUTER JOIN second_table ON first_table.item_id = second_table.item_id;
```

####  Correct Example #3
```sql
SELECT * FROM
    first_table
    FULL OUTER JOIN second_table ON first_table.item_id = second_table.item_id;
```

#### Additional Validations
```sql
SELECT * FROM t1;
```
