# IR-multiline-function-layout

Multiline function calls and single-row VALUES lists should put every direct argument on its own indented line and align the closing parenthesis with the caller.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: No
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `indent_size` (Default: `4`): Spaces added for function arguments. *Note: Value dynamically inherited from rule [`IR-indent`](../general/IR-indent.md) -> `indent_size` if not configured.*

#### ❌ Violating Example
```sql
coalesce(item_count,
0)
```

####  Correct Example
```sql
coalesce(
    item_count,
    0
)
```

#### Additional Validations
```sql
sum(item_count)
```

```sql
coalesce(item_count, 0)
```
