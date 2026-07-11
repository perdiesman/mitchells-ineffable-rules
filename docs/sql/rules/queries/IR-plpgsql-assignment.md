# IR-plpgsql-assignment

PL/pgSQL variable and trigger field assignments must use the standard assignment operator (:=).

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
NEW.file_uploader = TRUE;
```

####  Correct Example
```sql
NEW.file_uploader := TRUE;
```

#### Additional Validations
```sql
NEW.resolution := 'BY_POINT';
```
