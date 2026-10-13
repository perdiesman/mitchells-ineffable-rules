# IR-final-newline

Java files end with exactly one line terminator.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled`: `true`

#### Executable Cases
##### missing newline — Fixed
```java
class Sample {}
```

Expected fixed output:
```java
class Sample {}

```

##### single newline — Accepted
```java
class Sample {}

```
