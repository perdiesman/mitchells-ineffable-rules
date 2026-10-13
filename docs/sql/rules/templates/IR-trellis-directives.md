# IR-trellis-directives

Validate Trellis template blocks and use canonical directive comment layout.

- **Auto-Fixable**: Sometimes
- **Enabled by Default**: Yes
- **Category**: Template Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: No
- **Trellis Safe**: Yes
- **Configuration Options**:
  - `enabled`: `true`

#### Executable Cases
##### canonical conditional — Accepted
```sql
SELECT item_id
FROM sample_table
-- trellis: if active_only
WHERE retired_at IS NULL
-- trellis: endif
```

##### directive layout — Fixed
```sql
SELECT item_id
FROM sample_table
--trellis:IF active_only
WHERE retired_at IS NULL
--trellis:ENDIF
```

Expected fixed output:
```sql
SELECT item_id
FROM sample_table
-- trellis: if active_only
WHERE retired_at IS NULL
-- trellis: endif
```

##### unclosed conditional — Not Fixed
```sql
SELECT item_id
FROM sample_table
-- trellis: if active_only
WHERE retired_at IS NULL;
```

##### unexpected branch — Reported
```sql
SELECT item_id FROM sample_table;
-- trellis: else
```
