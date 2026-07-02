# IR-line-length

Lines must not exceed the configured maximum length.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Default Configuration**:
  - `enabled`: `true`
  - `max_length`: `120`

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
