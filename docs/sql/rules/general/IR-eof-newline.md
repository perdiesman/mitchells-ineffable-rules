# IR-eof-newline

Enforce that every SQL file ends with exactly one newline character.

- **Auto-Fixable**: Yes
- **Enabled by Default**: No
- **Category**: General Rules
- **Configuration Options**:
  - `enabled`: `false`

#### ❌ Violating Example #1
```sql
SELECT * FROM users;
```

####  Correct Example #1
```sql
SELECT * FROM users;

```

#### ❌ Violating Example #2
```sql
SELECT * FROM users;



```

####  Correct Example #2
```sql
SELECT * FROM users;

```
