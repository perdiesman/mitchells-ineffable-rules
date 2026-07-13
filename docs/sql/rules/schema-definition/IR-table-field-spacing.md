# IR-table-field-spacing

Enforce exactly one space (no alignment padding) between column/field names and their data types across table column definitions, parameters, and variable declarations.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Schema Definition Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
CREATE TEMP TABLE t (
    id       INTEGER,
    name     TEXT
);
```

####  Correct Example
```sql
CREATE TEMP TABLE t (
    id INTEGER,
    name TEXT
);
```
