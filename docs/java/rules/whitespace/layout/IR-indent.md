# IR-indent

Indent Java blocks and continuations with configurable four-space levels.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Whitespace and Layout
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `indent_size` (Default: `4`): Spaces per Java block level.
  - `continuation_indent` (Default: `4`): Additional spaces for wrapped constructs.

#### Default `BINARY_OPERATORS`
`!=`, `%`, `%=`, `&`, `&&`, `&=`, `*`, `*=`, `+`, `+=`, `-`, `-=`, `->`, `/`, `/=`, `:`, `<`, `<<`, `<<=`, `<=`, `=`, `==`, `>`, `>=`, `>>`, `>>=`, `>>>`, `>>>=`, `?`, `^`, `^=`, `|`, `|=`, `||`

#### Default `CONTAINER_TYPES`
`annotation_type_body`, `block`, `class_body`, `constructor_body`, `enum_body`, `interface_body`, `switch_block`

#### Default `CONTINUATION_TYPES`
`annotation_argument_list`, `argument_list`, `array_initializer`, `assignment_expression`, `binary_expression`, `formal_parameters`, `interfaces`, `method_invocation`, `parenthesized_expression`, `permits`, `record_header`, `resource_specification`, `super_interfaces`, `superclass`, `ternary_expression`, `throws`, `variable_declarator`

#### Default `CONTROL_KEYWORDS`
`catch`, `for`, `if`, `switch`, `synchronized`, `try`, `while`

#### Default `LIST_NODE_TYPES`
`annotation_argument_list`, `argument_list`, `formal_parameters`, `record_header`

#### Default `STATEMENT_TYPES`
`assert_statement`, `break_statement`, `continue_statement`, `expression_statement`, `local_variable_declaration`, `return_statement`, `throw_statement`, `yield_statement`

#### Executable Cases
##### nested block — Fixed
```java
class Sample {
  void execute() {
      if (ready) {
       run();
      }
  }
}

```

Expected fixed output:
```java
class Sample {
    void execute() {
        if (ready) {
            run();
        }
    }
}

```

##### multiline arguments — Fixed
```java
class Sample {
    void execute() {
        publish(
          first,
          second
        );
    }
}

```

Expected fixed output:
```java
class Sample {
    void execute() {
        publish(
            first,
            second
        );
    }
}

```

##### constructor body — Fixed
```java
class Sample {
    Sample(
        int value
    ) {
    this.value = value;
    }
    int value;
}

```

Expected fixed output:
```java
class Sample {
    Sample(
        int value
    ) {
        this.value = value;
    }
    int value;
}

```

##### assignment continuation — Fixed
```java
class Sample {
    void execute() {
        String value =
        createValue();
    }
    String createValue() { return "value"; }
}

```

Expected fixed output:
```java
class Sample {
    void execute() {
        String value =
            createValue();
    }
    String createValue() { return "value"; }
}

```
