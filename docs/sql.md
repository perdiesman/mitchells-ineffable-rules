# SQL Style Guide & Rules

This document describes all SQL linting rules supported by Mitchell's Ineffable Rules (IR) Linter.

## General Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-line-length`](#ir-line-length) | Lines must not exceed the configured maximum length. | No | [View Details](#ir-line-length) |
| [`IR-keyword-case`](#ir-keyword-case) | SQL keywords must be in uppercase. | Yes | [View Details](#ir-keyword-case) |

### IR-line-length

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

---
### IR-keyword-case

SQL keywords must be in uppercase.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Default Configuration**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
select id, username from users where active = true;
```

####  Correct Example
```sql
SELECT id, username FROM users WHERE active = true;
```

---

## Select / View / Materialized View Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| *No rules active* | *Future select/view/materialized view rules will be listed here* | - | - |

## Function / Procedure Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| *No rules active* | *Future function/procedure rules will be listed here* | - | - |

## Insert / Update / Delete Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| *No rules active* | *Future insert/update/delete rules will be listed here* | - | - |
