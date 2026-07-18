# IR-function-body-indent

Standardize indentation of PL/pgSQL function bodies relative to the AS tag.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Routine & Procedure Rules
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
