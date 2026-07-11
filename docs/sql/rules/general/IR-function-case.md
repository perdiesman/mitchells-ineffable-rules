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

#### ❌ Violating Example
```sql
SELECT COUNT(id), Sum(price) FROM orders;
```

####  Correct Example
```sql
SELECT count(id), sum(price) FROM orders;
```
