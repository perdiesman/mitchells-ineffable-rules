# IR-additive-wrap

Long additive expressions should wrap before an operator, with all continuation operators aligned one indentation level in. Under-indented subtraction and operands following a trailing multiplicative operator align with their surrounding expression.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Query Structure Rules
- **Commit Profile**: Yes
- **MyBatis Safe**: Yes
- **Trellis Safe**: No
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_line_length` (Default: `100`): Line length threshold for wrapping additive expressions.
  - `continuation_max_line_length` (Default: `120`): Line length threshold for an already-wrapped additive continuation.

#### ❌ Violating Example #1
```sql
                            first_measure + second_measure + third_measure + fourth_measure + fifth_measure_with_a_long_name,
```

####  Correct Example #1
```sql
                            first_measure + second_measure + third_measure + fourth_measure
                                + fifth_measure_with_a_long_name,
```

#### ❌ Violating Example #2
```sql
    first_measure + second_measure
           + third_measure +
                 fourth_measure
```

####  Correct Example #2
```sql
    first_measure + second_measure
        + third_measure + fourth_measure
```

#### ❌ Violating Example #3
```sql
    first_measure
        + second_measure
        + third_measure_with_a_long_name + fourth_measure
```

####  Correct Example #3
```sql
    first_measure + second_measure
        + third_measure_with_a_long_name + fourth_measure
```

#### ❌ Violating Example #4
```sql
                        recorded_at > #{selectedTime}::TIMESTAMP WITH TIME ZONE - window_hours * INTERVAL '1 hour'
```

####  Correct Example #4
```sql
                        recorded_at > #{selectedTime}::TIMESTAMP WITH TIME ZONE
                            - window_hours * INTERVAL '1 hour'
```

#### Additional Validations
```sql
SELECT first_measure + second_measure FROM sample_measure;
```

```sql
SELECT -very_long_negative_literal_operand_that_must_not_be_split_from_its_unary_sign;
```
