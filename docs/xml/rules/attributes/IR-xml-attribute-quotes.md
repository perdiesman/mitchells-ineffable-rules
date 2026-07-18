# IR-xml-attribute-quotes

Enforce double quotes around attribute values instead of single quotes.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Attributes
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```xml
<root attr='value' />
```

####  Correct Example
```xml
<root attr="value" />
```

#### Additional Validations
```xml
<root attr="value" />
```

```xml
<root attr="val &quot;quote&quot;" />
```
