# IR-paren-content-indent

Content inside multi-line parentheses should be indented 4 spaces relative to the opening parenthesis, and the closing parenthesis should align with it.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT COALESCE(
a,
b
) FROM users;
```

####  Correct Example
```sql
SELECT COALESCE(
    a,
    b
) FROM users;
```

#### Additional Validations
```sql
SELECT COALESCE(a, b) FROM users;
```
