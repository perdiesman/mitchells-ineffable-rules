# IR-paren-content-indent

Content inside multi-line parentheses should be indented 4 spaces relative to the opening parenthesis, and the closing parenthesis should align with it.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: No
- **MyBatis Safe**: No
- **Trellis Safe**: No
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
SELECT (
a +
b
) FROM users;
```

####  Correct Example #1
```sql
SELECT (
    a +
    b
) FROM users;
```

#### ❌ Violating Example #2
```sql
SELECT COALESCE(
a,
b
) FROM users;
```

####  Correct Example #2
```sql
SELECT COALESCE(
    a,
    b
) FROM users;
```

#### ❌ Violating Example #3
```sql
INSERT INTO t (c) VALUES
(1),
    (2);
```

####  Correct Example #3
```sql
INSERT INTO t(c) VALUES
    (1),
    (2);
```

#### Additional Validations
```sql
SELECT COALESCE(a, b) FROM users;
```

```sql
SELECT (a + b) FROM users;
```

```sql
INSERT INTO t(c) VALUES (1);
```

```sql
INSERT INTO t(c) VALUES
    (1),
    (2);
```

```sql
IMPORT FOREIGN SCHEMA sample_remote LIMIT TO (sample_table) FROM SERVER sample_server INTO sample_local;
```
