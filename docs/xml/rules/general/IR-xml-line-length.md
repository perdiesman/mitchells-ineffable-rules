# IR-xml-line-length

XML lines must not exceed the configured maximum length.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum line length limit.

#### ❌ Violating Example
```xml
<myTag firstAttribute="some_long_value_to_exceed_one_hundred_and_twenty_characters" secondAttribute="another_value_to_be_sure" />
```

####  Correct Example
```xml
<myTag firstAttribute="some_long_value_to_exceed_one_hundred_and_twenty_characters"
        secondAttribute="another_value_to_be_sure" />
```

#### Additional Validations
```xml
<root />
```
