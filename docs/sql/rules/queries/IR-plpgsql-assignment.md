# IR-plpgsql-assignment

PL/pgSQL variable and trigger field assignments must use the standard assignment operator (:=).

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
BEGIN
    NEW.file_uploader := TRUE;
END;
```

####  Correct Example #1
```sql
BEGIN
    NEW.file_uploader = TRUE;
END;
```

#### ❌ Violating Example #2
```sql
DECLARE
    my_var INT = 1;
BEGIN
END;
```

####  Correct Example #2
```sql
DECLARE
    my_var INT := 1;
BEGIN
END;
```

#### Additional Validations
```sql
BEGIN
    NEW.resolution = 'BY_POINT';
END;
```
