# IR-keyword-case

SQL keywords must be in uppercase.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `additional_keywords` (Default: `[]`): Additional SQL keywords to check/uppercase on top of defaults.
  - `override_keywords` (Default: `None`): Override the default list of SQL keywords entirely.

#### ❌ Violating Example
```sql
select id, username from users where active = true;
```

####  Correct Example
```sql
SELECT id, username FROM users WHERE active = true;
```
