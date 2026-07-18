# IR-xml-well-formed

Ensure that XML content is well-formed.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```xml
<root>
    <child>
</root>
```

####  Correct Example
```xml
<root>
    <child />
</root>
```

#### Additional Validations
```xml
<?xml version="1.0" encoding="utf-8"?>
<root />
```
