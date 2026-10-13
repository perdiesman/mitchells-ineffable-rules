# IR-xml-sql-entities

Raw greater-than characters in MyBatis SQL text must be encoded as &gt;; XML tags, attributes, comments, and CDATA remain unchanged.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Queries Rules
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled`: `true`

#### Default `MYBATIS_SQL_TAGS`
`delete`, `insert`, `select`, `sql`, `update`

#### ❌ Violating Example
```xml
<select id="items">SELECT payload -> 'name' FROM sample_item WHERE item_count > 0</select>
```

####  Correct Example
```xml
<select id="items">SELECT payload -&gt; 'name' FROM sample_item WHERE item_count &gt; 0</select>
```

#### Additional Validations
```xml
<select id="items">SELECT payload -&gt;&gt; 'name' FROM sample_item</select>
```

```xml
<if test="itemCount > 0">AND item_count &gt; 0</if>
```
