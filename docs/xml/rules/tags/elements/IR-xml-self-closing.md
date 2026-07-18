# IR-xml-self-closing

Enforce exactly one space before self-closing tag endings (e.g. <tag />).

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Tags and Elements
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example #1
```xml
<root/>
```

####  Correct Example #1
```xml
<root />
```

#### ❌ Violating Example #2
```xml
<root  />
```

####  Correct Example #2
```xml
<root />
```

#### Additional Validations
```xml
<root />
```

```xml
<root attr="val" />
```
