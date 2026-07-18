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
| [`IR-xml-indent`](rules/general/IR-xml-indent.md) | Enforce correct tag nesting indentation in XML files. | Yes | [View Details](rules/general/IR-xml-indent.md) |
| [`IR-xml-line-length`](rules/general/IR-xml-line-length.md) | XML lines must not exceed the configured maximum length. | No | [View Details](rules/general/IR-xml-line-length.md) |
| [`IR-xml-well-formed`](rules/general/IR-xml-well-formed.md) | Ensure that XML content is well-formed. | No | [View Details](rules/general/IR-xml-well-formed.md) |

## Tags and Elements

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-xml-self-closing`](rules/tags/elements/IR-xml-self-closing.md) | Enforce exactly one space before self-closing tag endings (e.g. <tag />). | Yes | [View Details](rules/tags/elements/IR-xml-self-closing.md) |

## Attributes

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-xml-attribute-quotes`](rules/attributes/IR-xml-attribute-quotes.md) | Enforce double quotes around attribute values instead of single quotes. | Yes | [View Details](rules/attributes/IR-xml-attribute-quotes.md) |

## Namespaces

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| *No rules active* | *Future namespaces rules will be listed here* | - | - |

## Queries Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-xml-mybatis-sql`](rules/queries/IR-xml-mybatis-sql.md) | Format embedded SQL inside MyBatis XML mapper files using SQL rules. | Yes | [View Details](rules/queries/IR-xml-mybatis-sql.md) |
