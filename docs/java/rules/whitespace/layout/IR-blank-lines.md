# IR-blank-lines

Do not start a Java file with a blank line or use consecutive blank lines.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Whitespace and Layout
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled`: `true`

#### Executable Cases
##### leading and repeated blank lines — Fixed
```java

class Sample {


    int value;
}

```

Expected fixed output:
```java
class Sample {

    int value;
}

```

##### single separator — Accepted
```java
class Sample {

    int value;
}

```
