# IR-paren-single

Unnecessary parentheses around a single condition should be removed.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: Yes
- **Intentional Semantic Rewrite**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: No
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
SELECT id FROM users WHERE (active = true);
```

####  Correct Example #1
```sql
SELECT id FROM users WHERE active = true;
```

#### ❌ Violating Example #2
```sql
SELECT (id)::integer FROM users;
```

####  Correct Example #2
```sql
SELECT id::integer FROM users;
```

#### Additional Validations
```sql
SELECT (a + b)::integer FROM users;
```

```sql
SELECT COALESCE(id, 0) FROM users;
```

```sql
SELECT id FROM users WHERE (active = true AND type = 'admin');
```

```sql
SELECT max(value) FILTER (WHERE active), ANY(:item_ids) FROM sample_item;
```

```sql
SELECT item_id FROM sample_item WHERE EXISTS (SELECT 1 FROM sample_child);
```

```sql
SELECT item_id FROM sample_item ORDER BY (rank <= :maximum_rank) DESC;
```

```sql
SELECT CAST(item_id AS TEXT) FROM sample_item;
```

```sql
SELECT item_id FROM sample_item WHERE item_id IN (:item_id);
```

```sql
SELECT item_id FROM sample_item JOIN sample_owner USING (owner_id);
```

```sql
SELECT (covered_count::NUMERIC / total_count) - 1 FROM sample_item;
```

```sql
INSERT INTO sample_item (item_id) VALUES (:item_id) ON CONFLICT (item_id) DO NOTHING;
```
