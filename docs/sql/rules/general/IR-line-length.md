# IR-line-length

Lines must not exceed the configured maximum length.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum line length limit.
  - `base_indent` (Default: `0`): Base indentation offset (in spaces or leading space string) to subtract before checking line lengths. *Note: Value dynamically inherited from rule [`IR-indent`](../general/IR-indent.md) -> `base_indent` if not configured.*

#### ❌ Violating Example
```sql
SELECT first_name, last_name, email, phone_number, mailing_address, date_of_birth, join_date, status, premium_member_flag FROM accounts_primary_table WHERE status = 'active';
```

####  Correct Example
```sql
SELECT
    first_name,
    last_name,
    email
FROM accounts_primary_table
WHERE status = 'active';
```
