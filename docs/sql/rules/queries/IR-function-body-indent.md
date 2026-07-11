# IR-function-body-indent

Standardize indentation of PL/pgSQL function bodies relative to the AS tag.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
AS $function$
    BEGIN
        RETURN NEW;
    END;
$function$;
```

####  Correct Example
```sql
AS $function$
BEGIN
    RETURN NEW;
END;
$function$;
```
