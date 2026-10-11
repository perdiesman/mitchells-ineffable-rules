# IR-member-spacing

Group adjacent fields and separate constructors, methods, initializers, and nested types with one blank line.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Classes and Interfaces
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
##### separate behavioral members — Fixed
```java
class Sample {
    int first;
    int second;
    Sample() {}
    void run() {}
}

```

Expected fixed output:
```java
class Sample {
    int first;
    int second;

    Sample() {}

    void run() {}
}

```

##### group fields — Accepted
```java
class Sample {
    int first;
    int second;
}

```
