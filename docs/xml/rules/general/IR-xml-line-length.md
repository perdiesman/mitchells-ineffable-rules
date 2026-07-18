# IR-xml-line-length

XML lines must not exceed the configured maximum length.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum line length limit.

#### ❌ Violating Example
```xml
<!-- AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA -->
```

####  Correct Example
```xml
<!-- Short line -->
```

#### Additional Validations
```xml
<root />
```
