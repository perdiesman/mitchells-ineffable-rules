# IR-additive-wrap

Long additive expressions should wrap before an operator, with all continuation operators aligned one indentation level in.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: No
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_line_length` (Default: `100`): Line length threshold for wrapping additive expressions.

#### ❌ Violating Example
```sql
                            first_measure + second_measure + third_measure + fourth_measure + fifth_measure_with_a_long_name,
```

####  Correct Example
```sql
                            first_measure + second_measure + third_measure + fourth_measure
                                + fifth_measure_with_a_long_name,
```

#### Additional Validations
```sql
SELECT first_measure + second_measure FROM sample_measure;
```

```sql
SELECT first_measure
    + second_measure FROM sample_measure;
```
