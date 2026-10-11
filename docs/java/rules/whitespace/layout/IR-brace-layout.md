# IR-brace-layout

Use K&R brace layout, multiline nonempty blocks, and joined else/catch/finally clauses.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Whitespace and Layout
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `indent_size` (Default: `4`): Spaces inside a nonempty block.

#### Default `BINARY_OPERATORS`
`!=`, `%`, `%=`, `&`, `&&`, `&=`, `*`, `*=`, `+`, `+=`, `-`, `-=`, `->`, `/`, `/=`, `:`, `<`, `<<`, `<<=`, `<=`, `=`, `==`, `>`, `>=`, `>>`, `>>=`, `>>>`, `>>>=`, `?`, `^`, `^=`, `|`, `|=`, `||`

#### Default `CONTAINER_TYPES`
`annotation_type_body`, `block`, `class_body`, `constructor_body`, `enum_body`, `interface_body`, `switch_block`

#### Default `CONTINUATION_TYPES`
`annotation_argument_list`, `argument_list`, `array_initializer`, `assignment_expression`, `binary_expression`, `formal_parameters`, `interfaces`, `method_invocation`, `permits`, `record_header`, `resource_specification`, `super_interfaces`, `superclass`, `ternary_expression`, `throws`, `variable_declarator`

#### Default `CONTROL_KEYWORDS`
`catch`, `for`, `if`, `switch`, `synchronized`, `try`, `while`

#### Default `LIST_NODE_TYPES`
`annotation_argument_list`, `argument_list`, `formal_parameters`, `record_header`

#### Default `STATEMENT_TYPES`
`assert_statement`, `break_statement`, `continue_statement`, `expression_statement`, `local_variable_declaration`, `return_statement`, `throw_statement`, `yield_statement`

#### Executable Cases
##### control block layout — Fixed
```java
class Sample
{
    void run()
    {
        if (ready) { execute(); }
        else { recover(); }
    }
}

```

Expected fixed output:
```java
class Sample {
    void run() {
        if (ready) {
            execute();
        } else {
            recover();
        }
    }
}

```

##### empty block — Accepted
```java
class Sample {
    void run() {}
}

```
