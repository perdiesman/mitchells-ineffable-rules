# IR-statement-blank-lines

Ensure at least one blank line between consecutive top-level SQL statements.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `min_blank_lines` (Default: `1`): Minimum number of blank lines between consecutive SQL statements.

#### ❌ Violating Example
```sql
SELECT 1;
SELECT 2;
```

####  Correct Example
```sql
SELECT 1;

SELECT 2;
```
