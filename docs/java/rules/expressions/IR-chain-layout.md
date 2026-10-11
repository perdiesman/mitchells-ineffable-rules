# IR-chain-layout

Keep fitting method chains compact; otherwise align each chained call one continuation level in.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Expressions
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum compact chain line length.
  - `indent_size` (Default: `4`): Chained-call continuation indentation.
  - `compact_if_fits` (Default: `true`): Collapse fitting chains.

#### Default `BINARY_OPERATORS`
`!=`, `%`, `%=`, `&`, `&&`, `&=`, `*`, `*=`, `+`, `+=`, `-`, `-=`, `->`, `/`, `/=`, `:`, `<`, `<<`, `<<=`, `<=`, `=`, `==`, `>`, `>=`, `>>`, `>>=`, `>>>`, `>>>=`, `?`, `^`, `^=`, `|`, `|=`, `||`

#### Default `CONTAINER_TYPES`
`annotation_type_body`, `block`, `class_body`, `constructor_body`, `enum_body`, `interface_body`, `switch_block`

#### Default `CONTINUATION_TYPES`
`annotation_argument_list`, `argument_list`, `array_initializer`, `assignment_expression`, `binary_expression`, `element_value_array_initializer`, `formal_parameters`, `interfaces`, `method_invocation`, `parenthesized_expression`, `permits`, `record_header`, `resource_specification`, `super_interfaces`, `superclass`, `ternary_expression`, `throws`, `variable_declarator`

#### Default `CONTROL_KEYWORDS`
`catch`, `for`, `if`, `switch`, `synchronized`, `try`, `while`

#### Default `LIST_NODE_TYPES`
`annotation_argument_list`, `argument_list`, `formal_parameters`, `record_header`

#### Default `STATEMENT_TYPES`
`assert_statement`, `break_statement`, `continue_statement`, `expression_statement`, `local_variable_declaration`, `return_statement`, `throw_statement`, `yield_statement`

#### Executable Cases
##### compact chain — Fixed
```java
class Sample {
    void run() {
        service
            .prepare()
            .execute();
    }
}

```

Expected fixed output:
```java
class Sample {
    void run() {
        service.prepare().execute();
    }
}

```

##### short chain — Accepted
```java
class Sample { void run() { service.prepare().execute(); } }

```

##### chain beginning with invocation — Fixed
```java
class Sample {
    String read() {
        return loadExtraordinarilyDescriptiveResponse(firstArgument, secondArgument, thirdArgument, fourthArgument).result().body().asText();
    }
}

```

Expected fixed output:
```java
class Sample {
    String read() {
        return loadExtraordinarilyDescriptiveResponse(firstArgument, secondArgument, thirdArgument, fourthArgument)
            .result()
            .body()
            .asText();
    }
}

```
