# IR-line-length

Java code should not exceed the configured line length; package, import, and text-block payload lines are exempt.

- **Auto-Fixable**: No
- **Enabled by Default**: Yes
- **Category**: General Rules
- **Commit Profile**: No
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `max_length` (Default: `120`): Maximum Java code line length.

#### Executable Cases
##### long statement — Reported
```java
class Sample {
    String value = createValueWithAnExcessivelyLongAndGenericMethodName(firstArgument, secondArgument, thirdArgument, fourthArgument);
}

```

##### short statement — Accepted
```java
class Sample {
    int value = 1;
}

```
