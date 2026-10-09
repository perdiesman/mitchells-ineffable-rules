# IR-table-function-indent

Indent multiline table-function arguments one level below FROM or JOIN and align the closing parenthesis with the function call.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `indent_size` (Default: `4`): Spaces added inside a multiline table-function call. *Note: Value dynamically inherited from rule [`IR-indent`](../general/IR-indent.md) -> `indent_size` if not configured.*

#### Executable Cases
##### multiline table function — Fixed
```sql
FROM sample.items_for_period(
        :period
    ) AS item
```

Expected fixed output:
```sql
FROM sample.items_for_period(
    :period
) AS item
```
