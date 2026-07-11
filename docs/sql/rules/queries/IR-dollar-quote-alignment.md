# IR-dollar-quote-alignment

Align the closing dollar quote ($function$, $$, etc.) with its opening tag.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
CREATE FUNCTION f() RETURNS void AS
$function$
    SELECT 1;
        $function$;
```

####  Correct Example
```sql
CREATE FUNCTION f() RETURNS void AS
$function$
    SELECT 1;
$function$;
```

#### Additional Validations
```sql
SELECT 'hello';
```
