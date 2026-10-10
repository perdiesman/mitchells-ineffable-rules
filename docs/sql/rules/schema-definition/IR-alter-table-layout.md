# IR-alter-table-layout

Long ALTER TABLE statements place the table action on a continuation line and expand constraint clauses without changing their tokens.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Schema Definition Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum line length before wrapping ALTER TABLE. *Note: Value dynamically inherited from rule [`IR-line-length`](../general/IR-line-length.md) -> `max_length` if not configured.*
  - `indent_size` (Default: `4`): Continuation indentation in spaces. *Note: Value dynamically inherited from rule [`IR-indent`](../general/IR-indent.md) -> `indent_size` if not configured.*

#### ❌ Violating Example
```sql
ALTER TABLE sample_item_history ADD CONSTRAINT sample_item_history_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES sample_owner (owner_id);
```

####  Correct Example
```sql
ALTER TABLE sample_item_history
    ADD CONSTRAINT sample_item_history_owner_id_fkey
        FOREIGN KEY (owner_id)
        REFERENCES sample_owner (owner_id);
```

#### Additional Validations
```sql
ALTER TABLE sample_item ADD COLUMN owner_id INTEGER;
```
