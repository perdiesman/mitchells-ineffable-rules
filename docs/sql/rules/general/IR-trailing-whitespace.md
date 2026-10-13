# IR-trailing-whitespace

Remove spaces and tabs at the ends of SQL lines.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: No
- **Trellis Safe**: Yes
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
SELECT item_id FROM sample_item;   

```

####  Correct Example
```sql
SELECT item_id FROM sample_item;

```

#### Additional Validations
```sql
SELECT item_id FROM sample_item;

```
