# IR-boolean-default

Enforce that boolean columns in table definitions explicitly define a DEFAULT constraint.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: Schema Definition Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
CREATE TABLE users (
    is_active BOOLEAN
);
```

####  Correct Example
```sql
CREATE TABLE users (
    is_active BOOLEAN DEFAULT false
);
```

#### Additional Validations
```sql
CREATE TABLE users (is_active BOOLEAN DEFAULT true);
```

```sql
CREATE TABLE users (id INTEGER, is_active BOOL NOT NULL DEFAULT false);
```
