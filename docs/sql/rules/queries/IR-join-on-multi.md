# IR-join-on-multi

Split AND or OR conditions in JOIN ON clauses to separate lines, indented 4 spaces.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT * FROM table_one JOIN table_two ON table_one.some_long_column_identifier = table_two.some_long_column_identifier AND table_one.another_long_column_identifier = table_two.another_long_column_identifier;
```

####  Correct Example
```sql
SELECT * FROM table_one JOIN table_two ON table_one.some_long_column_identifier = table_two.some_long_column_identifier
    AND table_one.another_long_column_identifier = table_two.another_long_column_identifier;
```

#### Additional Validations
```sql
SELECT * FROM t1 JOIN t2 ON t1.id = t2.id;
```
