# IR-assignment-layout

Keep fitting assignments compact; otherwise place the assigned value one continuation level after the operator.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Expressions
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum compact assignment line length.
  - `indent_size` (Default: `4`): Assigned-value continuation indentation.

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
##### long initializer — Fixed
```java
class Sample {
    List<ExtraordinarilyDescriptiveResult> descriptiveResults = (List<ExtraordinarilyDescriptiveResult>) cache.getIfPresent(cacheKey);
}

```

Expected fixed output:
```java
class Sample {
    List<ExtraordinarilyDescriptiveResult> descriptiveResults =
        (List<ExtraordinarilyDescriptiveResult>) cache.getIfPresent(cacheKey);
}

```

##### compact assignment — Accepted
```java
class Sample { int count = 1; }

```
