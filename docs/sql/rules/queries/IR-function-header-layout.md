# IR-function-header-layout

Standardize formatting, line-wrapping, and indentation of function creation headers.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum line length before wrapping clauses.

#### ❌ Violating Example
```sql
CREATE OR REPLACE FUNCTION my_func()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
```

####  Correct Example
```sql
CREATE OR REPLACE FUNCTION my_func() RETURNS trigger LANGUAGE plpgsql AS
$function$
```
