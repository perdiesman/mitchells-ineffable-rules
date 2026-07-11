# IR-function-case

Function names should be the same case (default lowercase).

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `case` (Default: `lowercase`): Target casing style for function names ('lowercase' or 'uppercase').
  - `additional_exclusions` (Default: `[]`): Additional keywords to exclude from function casing checks.
  - `override_exclusions` (Default: `None`): Override the default list of excluded keywords entirely.

#### Default `EXCLUDED_WORDS`
`all`, `and`, `any`, `array`, `as`, `between`, `by`, `case`, `distinct`, `else`, `end`, `except`, `exists`, `from`, `group`, `having`, `if`, `in`, `intersect`, `join`, `like`, `limit`, `not`, `offset`, `on`, `or`, `order`, `over`, `partition`, `recursive`, `return`, `row`, `select`, `some`, `table`, `then`, `union`, `using`, `values`, `when`, `where`, `while`, `window`, `with`

#### ❌ Violating Example
```sql
SELECT COUNT(id), Sum(price) FROM orders;
```

####  Correct Example
```sql
SELECT count(id), sum(price) FROM orders;
```
