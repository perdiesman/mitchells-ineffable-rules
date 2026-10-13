# IR-boolean-comparison

Standardize boolean comparison predicates to use idiomatic boolean predicates.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: Yes
- **Intentional Semantic Rewrite**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: Yes
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
SELECT * FROM users WHERE active = true AND blocked = false;
```

####  Correct Example #1
```sql
SELECT * FROM users WHERE active AND NOT blocked;
```

#### ❌ Violating Example #2
```sql
SELECT * FROM users WHERE active != true OR blocked <> false;
```

####  Correct Example #2
```sql
SELECT * FROM users WHERE NOT active OR blocked;
```

#### ❌ Violating Example #3
```sql
SELECT id FROM sample WHERE coalesce(enabled, false) = false AND #{includeHidden} = true;
```

####  Correct Example #3
```sql
SELECT id FROM sample WHERE NOT coalesce(enabled, false) AND #{includeHidden};
```

#### ❌ Violating Example #4
```sql
SELECT id FROM sample WHERE (#{scope} = 'all') IS TRUE;
```

####  Correct Example #4
```sql
SELECT id FROM sample WHERE (#{scope} = 'all');
```

#### Additional Validations
```sql
SELECT enabled = TRUE AS is_enabled FROM sample;
```

```sql
UPDATE sample SET enabled = FALSE WHERE id = 1;
```

```sql
SELECT id FROM sample WHERE FALSE = ANY(flags);
```
