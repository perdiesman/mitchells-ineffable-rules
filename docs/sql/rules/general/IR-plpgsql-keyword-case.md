# IR-plpgsql-keyword-case

Procedural PL/pgSQL keywords and trigger variables must be in uppercase.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Configuration Options**:
  - `enabled`: `true`

#### Default `PLPGSQL_KEYWORDS`
`AFTER`, `ALIAS`, `BEFORE`, `BEGIN`, `CALL`, `CASCADE`, `CONSTANT`, `CONTINUE`, `COST`, `DEBUG`, `DECLARE`, `DEFAULT`, `DEFINER`, `DIAGNOSTICS`, `EACH`, `ELSE`, `ELSIF`, `END`, `EXCEPTION`, `EXECUTE`, `EXIT`, `FOR`, `FOREACH`, `FOUND`, `FUNCTION`, `GET`, `IF`, `IMMUTABLE`, `INFO`, `INSTEAD`, `INVOKER`, `LANGUAGE`, `LEAKPROOF`, `LOG`, `LOOP`, `NEW`, `NOTICE`, `OF`, `OLD`, `OWNER`, `PARALLEL`, `PERFORM`, `PROCEDURE`, `QUERY`, `RAISE`, `RECORD`, `RESTRICTED`, `RETURN`, `RETURNS`, `REVERSE`, `ROW`, `ROWS`, `ROW_COUNT`, `SAFE`, `SECURITY`, `STABLE`, `STATEMENT`, `STRICT`, `TG_ARGV`, `TG_LEVEL`, `TG_NAME`, `TG_NARGS`, `TG_OP`, `TG_RELID`, `TG_RELNAME`, `TG_TABLE_NAME`, `TG_TABLE_SCHEMA`, `TG_WHEN`, `THEN`, `TO`, `TRIGGER`, `UNSAFE`, `USING`, `VOLATILE`, `WARNING`, `WHILE`

#### ❌ Violating Example
```sql
if new.manager then new.file_uploader = TRUE; end if;
```

####  Correct Example
```sql
IF NEW.manager THEN NEW.file_uploader = TRUE; END IF;
```
