# IR-unresolved-alias

Detect references to table aliases or qualifiers that are not declared in the query context.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT z.id FROM outage_data.zipcode;
-- z is not declared
```

####  Correct Example
```sql
SELECT z.id FROM outage_data.zipcode z;
```

#### Additional Validations
```sql
SELECT c.id FROM outage_data.county c;
```

```sql
SELECT NEW.id;
```
