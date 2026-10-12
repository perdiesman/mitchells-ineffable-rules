# IR-spacing

Use canonical spaces around Java operators, separators, and control parentheses.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Whitespace and Layout
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled`: `true`

#### Default `BINARY_OPERATORS`
`!=`, `%`, `%=`, `&`, `&&`, `&=`, `*`, `*=`, `+`, `+=`, `-`, `-=`, `->`, `/`, `/=`, `:`, `<`, `<<`, `<<=`, `<=`, `=`, `==`, `>`, `>=`, `>>`, `>>=`, `>>>`, `>>>=`, `?`, `^`, `^=`, `|`, `|=`, `||`

#### Default `CONTAINER_TYPES`
`annotation_type_body`, `block`, `class_body`, `constructor_body`, `enum_body`, `interface_body`, `switch_block`

#### Default `CONTINUATION_TYPES`
`annotation_argument_list`, `argument_list`, `array_initializer`, `assignment_expression`, `binary_expression`, `element_value_array_initializer`, `element_value_pair`, `formal_parameters`, `interfaces`, `method_invocation`, `parenthesized_expression`, `permits`, `record_header`, `resource_specification`, `super_interfaces`, `superclass`, `ternary_expression`, `throws`, `variable_declarator`

#### Default `CONTROL_KEYWORDS`
`catch`, `for`, `if`, `switch`, `synchronized`, `try`, `while`

#### Default `LIST_NODE_TYPES`
`annotation_argument_list`, `argument_list`, `formal_parameters`, `record_header`

#### Default `STATEMENT_TYPES`
`assert_statement`, `break_statement`, `continue_statement`, `expression_statement`, `local_variable_declaration`, `return_statement`, `throw_statement`, `yield_statement`

#### Executable Cases
##### control and operator spacing — Fixed
```java
class Sample {
    boolean test(int first,int second) {
        if(first==second){ return true; }
        return false;
    }
}

```

Expected fixed output:
```java
class Sample {
    boolean test(int first, int second) {
        if (first == second) { return true; }
        return false;
    }
}

```

##### method invocation — Accepted
```java
class Sample { void run() { call(first, second); } }

```
