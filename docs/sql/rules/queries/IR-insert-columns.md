# IR-insert-columns

Ensure INSERT statements explicitly list target columns.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```sql
INSERT INTO users VALUES (1, 'Alice');
```

####  Correct Example #1
```sql
INSERT INTO users (id, name) VALUES (1, 'Alice');
```

#### ❌ Violating Example #2
```sql
INSERT INTO users SELECT * FROM temp_users;
```

####  Correct Example #2
```sql
INSERT INTO users (id, name) SELECT id, name FROM temp_users;
```

#### Additional Validations
```sql
INSERT INTO schema.users (id, name) VALUES (1, 'Alice');
```

```sql
INSERT INTO users (id) SELECT id FROM temp_users;
```
