# IR-xml-mybatis-blank-lines

Remove boundary blank lines from MyBatis statements and limit internal blank-line runs to one.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Queries Rules
- **Commit Profile**: Yes
- **Configuration Options**:
  - `enabled`: `true`

#### Executable Cases
##### statement boundary blank lines — Fixed
```xml
<mapper namespace="Generic">
    <select id="items">

        SELECT item_id


        FROM sample_item

    </select>
</mapper>
```

Expected fixed output:
```xml
<mapper namespace="Generic">
    <select id="items">
        SELECT item_id

        FROM sample_item
    </select>
</mapper>
```

##### blank line before SQL closing parenthesis — Fixed
```xml
<mapper namespace="Generic">
    <select id="items">
        SELECT *
        FROM (
            SELECT item_id
            FROM sample_item

        ) items
    </select>
</mapper>
```

Expected fixed output:
```xml
<mapper namespace="Generic">
    <select id="items">
        SELECT *
        FROM (
            SELECT item_id
            FROM sample_item
        ) items
    </select>
</mapper>
```
