# IR-parameter-layout

Keep fitting method, constructor, lambda, and record parameters compact; otherwise use one parameter per line.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Method Declarations
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum compact line length.
  - `indent_size` (Default: `4`): Continuation indentation.
  - `compact_if_fits` (Default: `true`): Collapse simple fitting lists.

#### Default `BINARY_OPERATORS`
`!=`, `%`, `%=`, `&`, `&&`, `&=`, `*`, `*=`, `+`, `+=`, `-`, `-=`, `->`, `/`, `/=`, `:`, `<`, `<<`, `<<=`, `<=`, `=`, `==`, `>`, `>=`, `>>`, `>>=`, `>>>`, `>>>=`, `?`, `^`, `^=`, `|`, `|=`, `||`

#### Default `CONTAINER_TYPES`
`annotation_type_body`, `block`, `class_body`, `enum_body`, `interface_body`, `switch_block`

#### Default `CONTINUATION_TYPES`
`argument_list`, `array_initializer`, `binary_expression`, `formal_parameters`, `interfaces`, `method_invocation`, `permits`, `record_header`, `resource_specification`, `super_interfaces`, `superclass`, `ternary_expression`, `throws`

#### Default `CONTROL_KEYWORDS`
`catch`, `for`, `if`, `switch`, `synchronized`, `try`, `while`

#### Default `LIST_NODE_TYPES`
`annotation_argument_list`, `argument_list`, `formal_parameters`, `record_header`

#### Default `STATEMENT_TYPES`
`assert_statement`, `break_statement`, `continue_statement`, `expression_statement`, `local_variable_declaration`, `return_statement`, `throw_statement`, `yield_statement`

#### Executable Cases
##### compact fitting parameters — Fixed
```java
class Sample {
    void publish(
        String first,
        String second
    ) {}
}

```

Expected fixed output:
```java
class Sample {
    void publish(String first, String second) {}
}

```

##### compact record header — Accepted
```java
record Sample(String name, int count) {}

```
