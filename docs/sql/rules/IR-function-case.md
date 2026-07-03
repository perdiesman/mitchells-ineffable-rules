# IR-function-case

Function names should be the same case (default lowercase). Default excluded keywords (which are not treated as functions even if followed by a parenthesis): in, values, exists, join, using, on, and, or, not, select, from, where, having, between, like, as, over, partition, by, window, group, order, limit, offset, union, all, intersect, except, distinct, with, recursive, case, when, then, else, end.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
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
