# IR-join-on-multi

Keep JOIN ON conditions inline when they fit; otherwise split AND or OR conditions onto aligned continuation lines.

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
SELECT * FROM table_one JOIN table_two ON table_one.some_long_column_identifier = table_two.some_long_column_identifier AND table_one.another_long_column_identifier = table_two.another_long_column_identifier;
```

####  Correct Example #1
```sql
SELECT * FROM table_one JOIN table_two ON table_one.some_long_column_identifier = table_two.some_long_column_identifier
    AND table_one.another_long_column_identifier = table_two.another_long_column_identifier;
```

#### ❌ Violating Example #2
```sql
SELECT item.id FROM sample_item item JOIN sample_window window ON item.created_at BETWEEN window.start_at
    AND window.end_at AND item.organization_identifier = window.organization_identifier;
```

####  Correct Example #2
```sql
SELECT item.id FROM sample_item item JOIN sample_window window
    ON item.created_at BETWEEN window.start_at AND window.end_at
    AND item.organization_identifier = window.organization_identifier;
```

#### ❌ Violating Example #3
```sql
SELECT item.id FROM sample_item item JOIN sample_owner owner ON owner.id = item.owner_id
    AND owner.active;
```

####  Correct Example #3
```sql
SELECT item.id FROM sample_item item JOIN sample_owner owner ON owner.id = item.owner_id AND owner.active;
```

#### Additional Validations
```sql
SELECT * FROM t1 JOIN t2 ON t1.id = t2.id;
```

```sql
SELECT DISTINCT ON (item.item_id) item.item_id FROM sample_item item;
```

```sql
SELECT * FROM t1 JOIN t2 ON t1.created_at BETWEEN t2.start_at AND t2.end_at;
```
