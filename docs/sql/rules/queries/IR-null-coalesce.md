# IR-null-coalesce

Standardize isolated explicit -1 fallback predicates to COALESCE(x, -1); preserve nullable-column equality and surrounding boolean precedence.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: Yes
- **Intentional Semantic Rewrite**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: No
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT * FROM users WHERE active = -1 OR active IS NULL;
```

####  Correct Example
```sql
SELECT * FROM users WHERE COALESCE(active, -1) = -1;
```

#### Additional Validations
```sql
SELECT * FROM t1 JOIN t2 ON t1.id = t2.id OR (t1.id IS NULL AND t2.id IS NULL);
```

```sql
SELECT * FROM items WHERE enabled AND owner_id = -1 OR owner_id IS NULL;
```

```sql
SELECT * FROM items WHERE owner_id = -1 OR owner_id IS NULL AND enabled;
```

```sql
SELECT * FROM items WHERE NOT owner_id = -1 OR owner_id IS NULL;
```
