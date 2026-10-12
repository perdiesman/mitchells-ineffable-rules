# XML Style Guide & Rules

This document describes all XML linting rules supported by Mitchell's Ineffable Rules (IR) Linter.

## Categories

- [General Rules](#general-rules)
- [Tags and Elements](#tags-and-elements)
- [Attributes](#attributes)
- [Namespaces](#namespaces)
- [Queries Rules](#queries-rules)

## General Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-xml-indent`](rules/general/IR-xml-indent.md) | Enforce correct tag nesting indentation in XML files, format reusable MyBatis projection fragments according to their SELECT include sites, align physical predicates beneath static MyBatis WHERE clauses, and keep a SQL statement terminator attached to its preceding foreach closing tag. | Yes | [View Details](rules/general/IR-xml-indent.md) |
| [`IR-xml-line-length`](rules/general/IR-xml-line-length.md) | XML lines must not exceed the configured maximum length, and repeated MyBatis foreach forms use the same expanded layout; overlong inline dynamic SQL blocks expand without changing their expressions. SQL inside dollar quotes wraps only at existing clause whitespace. A self-closing marker moves to its own aligned line when keeping it with the final attribute would exceed the limit. Opaque XML text remains unchanged and is reported as non-fixable. | Yes | [View Details](rules/general/IR-xml-line-length.md) |
| [`IR-xml-well-formed`](rules/general/IR-xml-well-formed.md) | Ensure that XML content is well-formed. | No | [View Details](rules/general/IR-xml-well-formed.md) |

## Tags and Elements

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-xml-self-closing`](rules/tags/elements/IR-xml-self-closing.md) | Enforce exactly one space before self-closing tag endings (e.g. <tag />). | Yes | [View Details](rules/tags/elements/IR-xml-self-closing.md) |

## Attributes

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-xml-attribute-quotes`](rules/attributes/IR-xml-attribute-quotes.md) | Enforce double quotes around attribute values and encode greater-than comparisons inside attributes. | Yes | [View Details](rules/attributes/IR-xml-attribute-quotes.md) |

## Namespaces

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| *No rules active* | *Future namespaces rules will be listed here* | - | - |

## Queries Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-xml-mybatis-blank-lines`](rules/queries/IR-xml-mybatis-blank-lines.md) | Remove boundary blank lines from MyBatis statements and limit blank-line runs in mapper and generator XML to one. | Yes | [View Details](rules/queries/IR-xml-mybatis-blank-lines.md) |
| [`IR-xml-mybatis-sql`](rules/queries/IR-xml-mybatis-sql.md) | Format embedded SQL inside MyBatis XML mapper files using SQL rules. | Yes | [View Details](rules/queries/IR-xml-mybatis-sql.md) |
| [`IR-xml-sql-entities`](rules/queries/IR-xml-sql-entities.md) | Raw greater-than characters in MyBatis SQL text must be encoded as &gt;; XML tags, attributes, comments, and CDATA remain unchanged. | Yes | [View Details](rules/queries/IR-xml-sql-entities.md) |
