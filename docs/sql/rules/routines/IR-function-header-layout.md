# IR-function-header-layout

Standardize formatting, line-wrapping, and indentation of function creation headers.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Routine & Procedure Rules
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `100`): Maximum line length before wrapping clauses.

#### ❌ Violating Example #1
```sql
CREATE OR REPLACE FUNCTION my_func()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
```

####  Correct Example #1
```sql
CREATE OR REPLACE FUNCTION my_func() RETURNS trigger LANGUAGE plpgsql AS
$function$
```

#### ❌ Violating Example #2
```sql
CREATE FUNCTION test_func()
AS $body$
BEGIN
    RETURN 1;
END;
$body$ LANGUAGE plpgsql STABLE RETURNS integer;
```

####  Correct Example #2
```sql
CREATE FUNCTION test_func() RETURNS integer LANGUAGE plpgsql STABLE AS
$body$
BEGIN
    RETURN 1;
END;
$body$;
```
