# IR-parameter-annotation-layout

Keep fitting parameter annotations compact; otherwise place each annotation and the declared type on its own line.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Method Declarations
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum compact parameter line length.
  - `indent_size` (Default: `4`): Parameter continuation indentation.
  - `compact_if_fits` (Default: `true`): Collapse fitting annotated parameters.

#### Default `BEHAVIOR_MEMBER_TYPES`
`annotation_type_declaration`, `class_declaration`, `constructor_body`, `constructor_declaration`, `enum_declaration`, `interface_declaration`, `method_declaration`, `record_declaration`, `static_initializer`

#### Default `COMMENT_TYPES`
`block_comment`, `line_comment`

#### Default `TYPE_BODY_TYPES`
`annotation_type_body`, `class_body`, `enum_body`, `interface_body`

#### Executable Cases
##### long annotated parameter — Fixed
```java
class Sample {
    void publish(
        @OptionalValue @RequestValue(name = "category", required = false) @Converted(format = "timestamp-with-zone") OffsetDateTime startTime
    ) {}
}

```

Expected fixed output:
```java
class Sample {
    void publish(
        @OptionalValue
        @RequestValue(name = "category", required = false)
        @Converted(format = "timestamp-with-zone")
        OffsetDateTime startTime
    ) {}
}

```

##### compact annotation — Accepted
```java
class Sample { void publish(@Named String value) {} }

```
