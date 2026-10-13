# IR-lambda-layout

Keep fitting lambda expressions compact and indent wrapped expression bodies after the arrow.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Expressions
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum compact lambda length.
  - `indent_size` (Default: `4`): Expression-body continuation indentation.
  - `compact_if_fits` (Default: `true`): Collapse fitting expression lambdas.

#### Default `BEHAVIOR_MEMBER_TYPES`
`annotation_type_declaration`, `class_declaration`, `constructor_body`, `constructor_declaration`, `enum_declaration`, `interface_declaration`, `method_declaration`, `record_declaration`, `static_initializer`

#### Default `COMMENT_TYPES`
`block_comment`, `line_comment`

#### Default `TYPE_BODY_TYPES`
`annotation_type_body`, `class_body`, `enum_body`, `interface_body`

#### Executable Cases
##### compact expression lambda — Fixed
```java
class Sample {
    Object map(Object value) {
        return apply(value ->
            transform(value));
    }
    Object apply(Object value) { return value; }
    Object transform(Object value) { return value; }
}

```

Expected fixed output:
```java
class Sample {
    Object map(Object value) {
        return apply(value -> transform(value));
    }
    Object apply(Object value) { return value; }
    Object transform(Object value) { return value; }
}

```

##### block lambda — Accepted
```java
class Sample { Object value = (Runnable) () -> {}; }

```
