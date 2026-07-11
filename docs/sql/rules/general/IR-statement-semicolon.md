# IR-statement-semicolon

Enforce that all top-level statements end with a trailing semicolon.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
CREATE TRIGGER trig1 BEFORE INSERT ON t1 FOR EACH ROW EXECUTE FUNCTION f1()
CREATE TRIGGER trig2 BEFORE INSERT ON t2 FOR EACH ROW EXECUTE FUNCTION f2()
```

####  Correct Example
```sql
CREATE TRIGGER trig1 BEFORE INSERT ON t1 FOR EACH ROW EXECUTE FUNCTION f1();
CREATE TRIGGER trig2 BEFORE INSERT ON t2 FOR EACH ROW EXECUTE FUNCTION f2();
```

#### Additional Validations
```sql
ALTER FUNCTION my_func OWNER TO eiadmin;
CREATE TRIGGER trig1 BEFORE INSERT ON t1 FOR EACH ROW EXECUTE FUNCTION f1();
```
