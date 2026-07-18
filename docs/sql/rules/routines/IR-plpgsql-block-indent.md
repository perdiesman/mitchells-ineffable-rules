# IR-plpgsql-block-indent

Enforce block structure indentation inside PL/pgSQL procedural code blocks.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Routine & Procedure Rules
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `indent_size` (Default: `4`): Indentation size in spaces. *Note: Value dynamically inherited from rule [`IR-indent`](../general/IR-indent.md) -> `indent_size` if not configured.*

#### ❌ Violating Example
```sql
IF (condition) THEN
RAISE NOTICE 'HERE';
END IF;
```

####  Correct Example
```sql
IF (condition) THEN
    RAISE NOTICE 'HERE';
END IF;
```

#### Additional Validations
```sql
IF (condition) THEN
    RAISE NOTICE 'HERE';
END IF;
```
