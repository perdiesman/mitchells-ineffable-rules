# IR-xml-attribute-quotes

Enforce double quotes around attribute values and encode greater-than comparisons inside attributes.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Attributes
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```xml
<root attr='value' />
```

####  Correct Example #1
```xml
<root attr="value" />
```

#### ❌ Violating Example #2
```xml
<if test="count > 0">value</if>
```

####  Correct Example #2
```xml
<if test="count &gt; 0">value</if>
```

#### Additional Validations
```xml
<root attr="value" />
```

```xml
<root attr="val &quot;quote&quot;" />
```

```xml
<if test="count &gt; 0">value</if>
```
