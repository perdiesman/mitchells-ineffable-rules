# IR-type-parameter-layout

Keep fitting generic type parameters compact; otherwise place each parameter on its own line.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Classes and Interfaces
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum compact declaration length.
  - `indent_size` (Default: `4`): Continuation indentation.
  - `compact_if_fits` (Default: `true`): Collapse fitting parameter lists.

#### Default `BEHAVIOR_MEMBER_TYPES`
`annotation_type_declaration`, `class_declaration`, `constructor_body`, `constructor_declaration`, `enum_declaration`, `interface_declaration`, `method_declaration`, `record_declaration`, `static_initializer`

#### Default `COMMENT_TYPES`
`block_comment`, `line_comment`

#### Default `TYPE_BODY_TYPES`
`annotation_type_body`, `class_body`, `enum_body`, `interface_body`

#### Executable Cases
##### expanded generic parameters — Fixed
```java
class Sample<
    First,
    Second
> {}

```

Expected fixed output:
```java
class Sample<First, Second> {}

```

##### long generic parameters — Accepted
```java
class Sample<FirstParameterWithLongName, SecondParameterWithLongName> {}

```
