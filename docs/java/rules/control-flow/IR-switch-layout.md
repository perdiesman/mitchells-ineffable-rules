# IR-switch-layout

Place switch cases and colon-style case statements on readable, consistently indented lines.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Control Flow
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum compact arrow-case length.
  - `indent_size` (Default: `4`): Case-body indentation.

#### Default `BEHAVIOR_MEMBER_TYPES`
`annotation_type_declaration`, `class_declaration`, `constructor_body`, `constructor_declaration`, `enum_declaration`, `interface_declaration`, `method_declaration`, `record_declaration`, `static_initializer`

#### Default `COMMENT_TYPES`
`block_comment`, `line_comment`

#### Default `TYPE_BODY_TYPES`
`annotation_type_body`, `class_body`, `enum_body`, `interface_body`

#### Executable Cases
##### colon switch groups — Fixed
```java
class Sample {
    int value(int code) {
        switch (code) { case 1: prepare(); return 1; default: return 0; }
    }
    void prepare() {}
}

```

Expected fixed output:
```java
class Sample {
    int value(int code) {
        switch (code) {
            case 1:
                prepare();
                return 1;
            default:
                return 0;
        }
    }
    void prepare() {}
}

```

##### arrow switch rules — Fixed
```java
class Sample {
    int value(int code) {
        return switch (code) { case 1 -> 1; default -> 0; };
    }
}

```

Expected fixed output:
```java
class Sample {
    int value(int code) {
        return switch (code) {
            case 1 -> 1;
            default -> 0;
        };
    }
}

```
