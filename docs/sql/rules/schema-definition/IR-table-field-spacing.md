# IR-table-field-spacing

Enforce exactly one space between column/field name and its data type.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Schema Definition Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
CREATE TEMP TABLE t (
    a      integer,
    b          text
);
```

####  Correct Example
```sql
CREATE TEMP TABLE t (
    a integer,
    b text
);
```

#### Additional Validations
```sql
CREATE TABLE t (a INTEGER);
```
