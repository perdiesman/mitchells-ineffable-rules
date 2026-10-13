# IR-enum-layout

Keep fitting enum constants together; otherwise place each constant on its own line.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Classes and Interfaces
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum compact constant line length.
  - `indent_size` (Default: `4`): Enum-body indentation.
  - `compact_if_fits` (Default: `true`): Keep fitting constants on one line.

#### Default `BEHAVIOR_MEMBER_TYPES`
`annotation_type_declaration`, `class_declaration`, `constructor_body`, `constructor_declaration`, `enum_declaration`, `interface_declaration`, `method_declaration`, `record_declaration`, `static_initializer`

#### Default `COMMENT_TYPES`
`block_comment`, `line_comment`

#### Default `TYPE_BODY_TYPES`
`annotation_type_body`, `class_body`, `enum_body`, `interface_body`

#### Executable Cases
##### compact constants — Fixed
```java
enum Status {
    READY,
    RUNNING,
    DONE
}

```

Expected fixed output:
```java
enum Status {
    READY, RUNNING, DONE
}

```

##### fitting constants — Accepted
```java
enum Status {
    READY, RUNNING, DONE
}

```
