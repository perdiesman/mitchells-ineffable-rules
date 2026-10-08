# IR-named-parameters

Enforce named parameter notation (:= or =>) in function calls with 3 or more arguments.

- **Auto-Fixable**: No
- **Enabled by Default**: No
- **Category**: Routine & Procedure Rules
- **Commit Profile**: No
- **MyBatis Safe**: Yes
- **Trellis Safe**: No
- **Configuration Options**:
  - `enabled`: `false`

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
