# IR-from-paren-layout

Parenthesized column alias lists in FROM/JOIN clauses should format entries one per line if the line exceeds max length.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_line_length` (Default: `140`): Line length threshold above which paren lists will be split. *Note: Value dynamically inherited from rule [`IR-line-length`](../general/IR-line-length.md) -> `max_line_length` if not configured.*

#### ❌ Violating Example
```sql
SELECT * FROM func() alias(col1, col2, col3, col4, col5, col6, col7, col8, col9, col10, col11, col12, col13, col14, col15, col16, col17, col18);
```

####  Correct Example
```sql
SELECT * FROM func() alias(
    col1,
    col2,
    col3,
    col4,
    col5,
    col6,
    col7,
    col8,
    col9,
    col10,
    col11,
    col12,
    col13,
    col14,
    col15,
    col16,
    col17,
    col18
);
```

#### Additional Validations
```sql
SELECT * FROM func() alias(col1, col2);
```
