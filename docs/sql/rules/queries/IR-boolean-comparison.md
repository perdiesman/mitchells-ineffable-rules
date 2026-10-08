# IR-boolean-comparison

Standardize boolean comparison predicates to use idiomatic boolean predicates.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: No
- **MyBatis Safe**: Yes
- **Trellis Safe**: No
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
