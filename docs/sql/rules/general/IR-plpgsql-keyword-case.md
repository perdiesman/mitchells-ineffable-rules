# IR-plpgsql-keyword-case

Procedural PL/pgSQL keywords and trigger variables must be in uppercase.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
if new.manager then new.file_uploader = TRUE; end if;
```

####  Correct Example
```sql
IF NEW.manager THEN NEW.file_uploader = TRUE; END IF;
```
