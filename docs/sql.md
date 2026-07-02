# SQL Style Guide & Rules

This document describes all SQL linting rules supported by Mitchell's Ineffable Rules (IR) Linter.

## Categories

- [General Rules](#general-rules)
- [Select / View / Materialized View Rules](#select-view-materialized-view-rules)
- [Function / Procedure Rules](#function-procedure-rules)
- [Insert / Update / Delete Rules](#insert-update-delete-rules)

## General Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-line-length`](#ir-line-length) | Lines must not exceed the configured maximum length. | No | [View Details](#ir-line-length) |
| [`IR-indent`](#ir-indent) | Indent should be equal amounts of spaces (default 4). | Yes | [View Details](#ir-indent) |
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
### IR-indent

Indent should be equal amounts of spaces (default 4).

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Default Configuration**:
  - `enabled`: `true`
  - `indent_size`: `4`

#### ❌ Violating Example
```sql
SELECT
  id,
   name
FROM users;
```

####  Correct Example
```sql
SELECT
    id,
    name
FROM users;
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
| [`IR-column-layout`](#ir-column-layout) | On select, order by, group by, if all the columns fit on one line then put them on one line, otherwise wrap one per line. | Yes | [View Details](#ir-column-layout) |
| [`IR-function-case`](#ir-function-case) | Function names should be the same case (default lowercase). | Yes | [View Details](#ir-function-case) |

### IR-column-layout

On select, order by, group by, if all the columns fit on one line then put them on one line, otherwise wrap one per line.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Default Configuration**:
  - `enabled`: `true`
  - `max_length`: `120`
  - `indent_size`: `4`

#### ❌ Violating Example
```sql
SELECT
    id,
    name
FROM users;
SELECT first_name, last_name, email, phone_number, mailing_address, date_of_birth, join_date, another_long_column_name, yet_another_one_to_be_sure FROM users;
```

####  Correct Example
```sql
SELECT id, name
FROM users;
SELECT
    first_name,
    last_name,
    email,
    phone_number,
    mailing_address,
    date_of_birth,
    join_date,
    another_long_column_name,
    yet_another_one_to_be_sure
FROM users;
```

---
### IR-function-case

Function names should be the same case (default lowercase).

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Select / View / Materialized View Rules
- **Default Configuration**:
  - `enabled`: `true`
  - `case`: `lowercase`

#### ❌ Violating Example
```sql
SELECT COUNT(id), Sum(price) FROM orders;
```

####  Correct Example
```sql
SELECT count(id), sum(price) FROM orders;
```

---

## Function / Procedure Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| *No rules active* | *Future function/procedure rules will be listed here* | - | - |

## Insert / Update / Delete Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| *No rules active* | *Future insert/update/delete rules will be listed here* | - | - |
