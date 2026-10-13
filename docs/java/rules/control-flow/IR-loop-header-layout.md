# IR-loop-header-layout

Keep fitting for-loop headers compact; otherwise place each logical header part on its own line.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Control Flow
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum compact header length.
  - `indent_size` (Default: `4`): Header continuation indentation.
  - `compact_if_fits` (Default: `true`): Collapse fitting loop headers.

#### Default `BEHAVIOR_MEMBER_TYPES`
`annotation_type_declaration`, `class_declaration`, `constructor_body`, `constructor_declaration`, `enum_declaration`, `interface_declaration`, `method_declaration`, `record_declaration`, `static_initializer`

#### Default `COMMENT_TYPES`
`block_comment`, `line_comment`

#### Default `TYPE_BODY_TYPES`
`annotation_type_body`, `class_body`, `enum_body`, `interface_body`

#### Executable Cases
##### expanded classic loop — Fixed
```java
class Sample {
    void run() {
        for (
            int index = 0;
            index < count;
            index++
        ) {}
    }
}

```

Expected fixed output:
```java
class Sample {
    void run() {
        for (int index = 0; index < count; index++) {}
    }
}

```

##### expanded enhanced loop — Fixed
```java
class Sample {
    void run() {
        for (
            String value :
            values
        ) {}
    }
}

```

Expected fixed output:
```java
class Sample {
    void run() {
        for (String value : values) {}
    }
}

```
