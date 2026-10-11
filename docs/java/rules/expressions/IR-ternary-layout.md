# IR-ternary-layout

Keep fitting ternary expressions compact; otherwise align question and colon branches.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Expressions
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum compact expression line length.
  - `indent_size` (Default: `4`): Ternary continuation indentation.
  - `compact_if_fits` (Default: `true`): Collapse fitting ternary expressions.

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
##### compact ternary — Fixed
```java
class Sample { int value(boolean ready) { return ready
        ? first()
        : second(); } int first() { return 1; } int second() { return 2; } }

```

Expected fixed output:
```java
class Sample { int value(boolean ready) { return ready ? first() : second(); } int first() { return 1; } int second() { return 2; } }

```

##### compact branch — Accepted
```java
class Sample { int value(boolean ready) { return ready ? 1 : 2; } }

```

##### nested ternary branches — Fixed
```java
class Sample {
    Result choose(State state) {
        return (state == State.FIRST) ? Result.FIRST : (state == State.SECOND) ? Result.SECOND : Result.EXTRAORDINARILY_LONG_FALLBACK_RESULT;
    }
}

```

Expected fixed output:
```java
class Sample {
    Result choose(State state) {
        return (state == State.FIRST)
            ? Result.FIRST
            : (state == State.SECOND)
                ? Result.SECOND
                : Result.EXTRAORDINARILY_LONG_FALLBACK_RESULT;
    }
}

```
