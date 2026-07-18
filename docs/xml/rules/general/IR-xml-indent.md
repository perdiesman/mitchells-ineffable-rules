# IR-xml-indent

Enforce correct tag nesting indentation in XML files.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `indent_size` (Default: `4`): Number of spaces for nesting indentation.

#### ❌ Violating Example
```xml
<root>
  <child />
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
<root>
    <child>
        <grandchild />
    </child>
</root>
```
