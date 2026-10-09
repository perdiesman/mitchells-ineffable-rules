# IR-between

Standardize range predicate check of form 'a >= b AND a <= c' to 'a BETWEEN b AND c'.

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
SELECT * FROM users WHERE age >= 18 AND age <= 65;
```

####  Correct Example #1
```sql
SELECT * FROM users WHERE age BETWEEN 18 AND 65;
```

#### ❌ Violating Example #2
```sql
SELECT * FROM users WHERE age <= 65 AND age >= 18;
```

####  Correct Example #2
```sql
SELECT * FROM users WHERE age BETWEEN 18 AND 65;
```

#### ❌ Violating Example #3
```sql
SELECT item_id FROM sample WHERE recorded_at >= timezone('utc', #{start}) AND recorded_at <= timezone('utc', #{end});
```

####  Correct Example #3
```sql
SELECT item_id FROM sample WHERE recorded_at BETWEEN timezone('utc', #{start}) AND timezone('utc', #{end});
```

#### Additional Validations
```sql
SELECT item_id FROM sample WHERE recorded_at >= #{start} OR recorded_at <= #{end};
```

```sql
SELECT item_id FROM sample WHERE lower_bound >= 1 AND upper_bound <= 10;
```

```sql
SELECT item_id FROM sample WHERE recorded_at >= #{start} AND -- retain rationale
recorded_at <= #{end};
```
