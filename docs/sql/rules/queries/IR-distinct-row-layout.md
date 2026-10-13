# IR-distinct-row-layout

A multi-column row used as the argument to multiline DISTINCT should put each field on its own indented line.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: No
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```sql
count(
    DISTINCT (state_id, utility_id, sub_utility_id)
)
```

####  Correct Example
```sql
count(
    DISTINCT (
        state_id,
        utility_id,
        sub_utility_id
    )
)
```

#### Additional Validations
```sql
count(DISTINCT (state_id, utility_id))
```

```sql
count(
    DISTINCT utility_id
)
```
