# IR-whitespace

Use spaces for indentation and remove trailing whitespace outside literals and comments.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Whitespace and Layout
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled` (Default: `true`): Enable or disable this rule.
  - `indent_size` (Default: `4`): Spaces represented by one indentation tab.

#### Executable Cases
##### indentation tab and trailing code space — Fixed
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

##### text block whitespace — Accepted
```java
class Sample {
    String value = """
        keep   
        """;
}

```
