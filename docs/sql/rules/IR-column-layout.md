# IR-column-layout

On select, order by, group by, if all the columns fit on one line then put them on one line, otherwise wrap one per line.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum line length limit used to determine if columns fit on a single line. *Note: Value dynamically inherited from rule [`IR-line-length`](IR-line-length.md) -> `max_length` if not configured.*
  - `indent_size` (Default: `4`): Number of spaces used for single-level column wrapping indentation. *Note: Value dynamically inherited from rule [`IR-indent`](IR-indent.md) -> `indent_size` if not configured.*
  - `base_indent` (Default: `0`): Base indentation level (in spaces or leading space string) of the outer container. *Note: Value dynamically inherited from rule [`IR-indent`](IR-indent.md) -> `base_indent` if not configured.*

#### ❌ Violating Example #1
```sql
SELECT
    id,
    name
FROM users;
```

####  Correct Example #1
```sql
SELECT id, name
FROM users;
```

#### ❌ Violating Example #2
```sql
SELECT first_name, last_name, email, phone_number, mailing_address, date_of_birth, join_date, another_long_column_name, yet_another_one_to_be_sure FROM users;
```

####  Correct Example #2
```sql
SELECT
    first_name,
    last_name,
    email,
    phone_number,
    mailing_address,
    date_of_birth,
    join_date,
    another_long_column_name,
    yet_another_one_to_be_sure FROM users;
```

#### Additional Validations
```sql
SELECT id, name FROM users;
```
