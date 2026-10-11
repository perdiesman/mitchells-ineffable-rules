# IR-array-initializer-layout

Keep fitting array initializers compact; otherwise place each value on its own line.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Variables and Fields
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum compact initializer line length.
  - `indent_size` (Default: `4`): Initializer continuation indentation.
  - `compact_if_fits` (Default: `true`): Collapse fitting initializers.

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
##### compact initializer — Fixed
```java
class Sample { int[] values = {
    1,
    2
}; }

```

Expected fixed output:
```java
class Sample { int[] values = {1, 2}; }

```

##### compact values — Accepted
```java
class Sample { int[] values = {1, 2}; }

```
