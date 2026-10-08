# IR-as-spacing

The AS keyword must be preceded by exactly one space.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: Yes
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT a   AS b FROM t;
```

####  Correct Example
```sql
SELECT a AS b FROM t;
```

#### Additional Validations
```sql
SELECT a AS b FROM t;
```

```sql
SELECT a
AS b FROM t;
```
