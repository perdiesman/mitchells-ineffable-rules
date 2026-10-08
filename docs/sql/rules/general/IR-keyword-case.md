# IR-keyword-case

SQL keywords must be in uppercase.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `additional_keywords` (Default: `[]`): Additional SQL keywords to check/uppercase on top of defaults.
  - `override_keywords` (Default: `None`): Override the default list of SQL keywords entirely.

#### Default `FUNCTION_KEYWORD_AMBIGUITIES`
`left`, `right`

#### Default `KEYWORDS`
`alter`, `and`, `as`, `case`, `create`, `delete`, `distinct`, `drop`, `else`, `end`, `from`, `group by`, `having`, `index`, `inner`, `insert`, `into`, `join`, `lateral`, `left`, `limit`, `on`, `or`, `order by`, `outer`, `recursive`, `right`, `select`, `set`, `table`, `then`, `union`, `update`, `values`, `when`, `where`, `with`

#### ❌ Violating Example
```sql
select id, username from users where active = true;
```

####  Correct Example
```sql
SELECT id, username FROM users WHERE active = true;
```
