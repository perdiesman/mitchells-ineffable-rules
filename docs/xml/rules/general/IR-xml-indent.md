# IR-xml-indent

Enforce correct tag nesting indentation in XML files, format reusable MyBatis projection fragments according to their SELECT include sites, align physical predicates beneath static MyBatis WHERE clauses, and keep a SQL statement terminator attached to its preceding foreach closing tag.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Commit Profile**: Yes
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
