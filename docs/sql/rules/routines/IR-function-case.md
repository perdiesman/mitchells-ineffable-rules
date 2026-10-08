# IR-function-case

Function names should be the same case (default lowercase).

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Routine & Procedure Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `case` (Default: `lowercase`): Target casing style for function names ('lowercase' or 'uppercase').
  - `additional_exclusions` (Default: `[]`): Additional keywords to exclude from function casing checks.
  - `override_exclusions` (Default: `None`): Override the default list of excluded keywords entirely.

#### Default `EXCLUDED_WORDS`
`all`, `and`, `any`, `array`, `as`, `between`, `bigint`, `bool`, `boolean`, `by`, `case`, `char`, `character`, `conflict`, `date`, `decimal`, `distinct`, `double`, `else`, `end`, `except`, `exists`, `filter`, `from`, `geometry`, `gist`, `group`, `having`, `if`, `in`, `int`, `integer`, `intersect`, `join`, `json`, `jsonb`, `lateral`, `like`, `limit`, `not`, `numeric`, `offset`, `on`, `or`, `order`, `over`, `partition`, `real`, `recursive`, `return`, `row`, `select`, `smallint`, `some`, `table`, `text`, `then`, `time`, `timestamp`, `timestamptz`, `timetz`, `union`, `using`, `uuid`, `values`, `varchar`, `varying`, `when`, `where`, `while`, `window`, `with`

#### Default `KEYWORD_FUNCTIONS`
`COALESCE`, `LEFT`, `RIGHT`

#### ❌ Violating Example
```sql
SELECT COUNT(id), Sum(price) FROM orders;
```

####  Correct Example
```sql
SELECT count(id), sum(price) FROM orders;
```
