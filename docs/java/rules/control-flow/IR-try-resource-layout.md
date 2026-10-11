# IR-try-resource-layout

Keep fitting try resources compact; otherwise place each resource on its own line.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Control Flow
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum compact resource line length.
  - `indent_size` (Default: `4`): Resource continuation indentation.
  - `compact_if_fits` (Default: `true`): Collapse fitting resource lists.

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
##### compact resources — Fixed
```java
class Sample { void run() throws Exception { try (
    var first = open();
    var second = open()
) {} } Object open() { return null; } }

```

Expected fixed output:
```java
class Sample { void run() throws Exception { try (var first = open(); var second = open()) {} } Object open() { return null; } }

```

##### single resource — Accepted
```java
class Sample { void run() throws Exception { try (var value = open()) {} } Object open() { return null; } }

```
