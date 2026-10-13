# IR-case

CASE statements should be formatted with WHEN/THEN on separate lines unless the block is simple (exactly one WHEN condition and an optional ELSE clause) and fits on a single line within length constraints. Nested CASE results stay attached to ELSE and indent as child blocks.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: No
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT CASE WHEN x = 1 THEN 'a' WHEN x = 2 THEN 'b' ELSE 'c' END FROM users;
```

####  Correct Example
```sql
SELECT 
    CASE
        WHEN x = 1 THEN 'a'
        WHEN x = 2 THEN 'b'
        ELSE 'c'
    END FROM users;
```

#### Additional Validations
```sql
SELECT CASE WHEN x = 1 THEN 'a' END FROM users;
```

```sql
SELECT CASE WHEN x = 1 THEN 'a' ELSE 'b' END FROM users;
```

```sql
SELECT 
    CASE
        WHEN x = 1 THEN 'a'
        WHEN x = 2 THEN 'b'
        ELSE 'c'
    END;
```

```sql
SELECT CASE WHEN x IS NULL THEN NULL ELSE CASE WHEN y = 1 THEN true ELSE false END END FROM users;
```

```sql
SELECT CASE
    WHEN group_id = 1 THEN group_name
    ELSE CASE
        WHEN group_id = 2 THEN option_name
        ELSE CASE WHEN group_id = 3 THEN style_name ELSE null END
    END
END AS display_name FROM sample_item;
```
