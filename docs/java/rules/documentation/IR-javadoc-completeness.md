# IR-javadoc-completeness

Keep existing public API Javadoc tags synchronized with method parameters, returns, and throws clauses.

- **Auto-Fixable**: No
- **Enabled by Default**: No
- **Category**: Documentation
- **Commit Profile**: No
- **Configuration Options**:
  - `enabled` (Default: `false`): Enable or disable this rule.
  - `severity` (Default: `warning`): Violation severity.

#### Default `WARNING_CONFIG`
- `severity`: `warning`

#### Default `WARNING_OPTION`
- `severity`: `{'default': 'warning', 'description': 'Violation severity.'}`

#### Executable Cases
##### missing parameter tag — Reported
```java
/** Returns a value.
 * @return the value
 */
public class Sample {
    /** Reads a value.
     * @return the value
     */
    public int read(String name) { return 1; }
}

```

##### complete method tags — Accepted
```java
public class Sample {
    /** Reads a value.
     * @param name requested name
     * @return the value
     */
    public int read(String name) { return 1; }
}

```
