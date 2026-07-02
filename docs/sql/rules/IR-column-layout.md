# IR-column-layout

On select, order by, group by, if all the columns fit on one line then put them on one line, otherwise wrap one per line.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Default Configuration**:
  - `enabled`: `true`
  - `max_length`: `120`
  - `indent_size`: `4`

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
