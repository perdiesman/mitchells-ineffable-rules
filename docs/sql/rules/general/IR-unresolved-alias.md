# IR-unresolved-alias

Detect references to table aliases or qualifiers that are not declared in the query context.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT t.id FROM my_schema.my_table;
-- t is not declared
```

####  Correct Example
```sql
SELECT t.id FROM my_schema.my_table t;
```

#### Additional Validations
```sql
SELECT o.id FROM other_schema.other_table o;
```

```sql
SELECT NEW.id;
```
