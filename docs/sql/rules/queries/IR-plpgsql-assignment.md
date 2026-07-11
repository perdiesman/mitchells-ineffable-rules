# IR-plpgsql-assignment

PL/pgSQL variable and trigger field assignments must use the standard assignment operator (:=).

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled`: `true`

#### Default `EXCLUDED_STARTERS`
`ALTER`, `ANALYZE`, `BEGIN`, `CALL`, `CASE`, `CLOSE`, `COMMIT`, `COPY`, `CREATE`, `DECLARE`, `DELETE`, `DROP`, `END`, `EXECUTE`, `EXPLAIN`, `FETCH`, `FOR`, `GET`, `GRANT`, `IF`, `INSERT`, `LOCK`, `LOOP`, `MOVE`, `OPEN`, `PERFORM`, `RAISE`, `REFRESH`, `REINDEX`, `RETURN`, `REVOKE`, `ROLLBACK`, `SELECT`, `TRUNCATE`, `UPDATE`, `VACUUM`, `WHILE`, `WITH`

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
