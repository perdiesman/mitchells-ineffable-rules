# IR-java-syntax

Java source must parse without missing or erroneous syntax nodes.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled`: `true`

#### Executable Cases
##### valid type — Accepted
```java
class Sample {}

```

##### missing type body — Reported
```java
class Sample {

```
