# IR-empty-body-layout

Write empty Java declaration and executable bodies as compact braces.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Whitespace and Layout
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled`: `true`

#### Default `BEHAVIOR_MEMBER_TYPES`
`annotation_type_declaration`, `class_declaration`, `constructor_body`, `constructor_declaration`, `enum_declaration`, `interface_declaration`, `method_declaration`, `record_declaration`, `static_initializer`

#### Default `COMMENT_TYPES`
`block_comment`, `line_comment`

#### Default `TYPE_BODY_TYPES`
`annotation_type_body`, `class_body`, `enum_body`, `interface_body`

#### Executable Cases
##### empty method body — Fixed
```java
class Sample {
    void reset() {
    }
}

```

Expected fixed output:
```java
class Sample {
    void reset() {}
}

```

##### commented body — Accepted
```java
class Sample {
    void reset() {
        // Deliberately empty.
    }
}

```
