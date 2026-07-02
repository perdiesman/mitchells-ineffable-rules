# SQL Style Guide & Rules

This document describes all SQL linting rules supported by Mitchell's Ineffable Rules (IR) Linter.

## Categories

- [General Rules](#general-rules)
- [Select / View / Materialized View Rules](#select-view-materialized-view-rules)
- [Function / Procedure Rules](#function-procedure-rules)
- [Insert / Update / Delete Rules](#insert-update-delete-rules)

## General Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-line-length`](rules/IR-line-length.md) | Lines must not exceed the configured maximum length. | No | [View Details](rules/IR-line-length.md) |
| [`IR-indent`](rules/IR-indent.md) | Indent should be equal amounts of spaces (default 4). | Yes | [View Details](rules/IR-indent.md) |
| [`IR-keyword-case`](rules/IR-keyword-case.md) | SQL keywords must be in uppercase. | Yes | [View Details](rules/IR-keyword-case.md) |

## Select / View / Materialized View Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-empty-command`](rules/IR-empty-command.md) | Remove empty SQL commands, such as duplicate semicolons or leading semicolons. | Yes | [View Details](rules/IR-empty-command.md) |
| [`IR-join-parens`](rules/IR-join-parens.md) | Unnecessary parentheses around a JOIN clause should be removed. | Yes | [View Details](rules/IR-join-parens.md) |
| [`IR-case-when-when`](rules/IR-case-when-when.md) | Remove duplicate adjacent WHEN keywords. | Yes | [View Details](rules/IR-case-when-when.md) |
| [`IR-clause-alignment`](rules/IR-clause-alignment.md) | Main query clause keywords (SELECT, FROM, WHERE, GROUP BY, HAVING, ORDER BY, LIMIT) must have the exact same indentation within the same query block when the query spans multiple lines. | Yes | [View Details](rules/IR-clause-alignment.md) |
| [`IR-column-layout`](rules/IR-column-layout.md) | On select, order by, group by, if all the columns fit on one line then put them on one line, otherwise wrap one per line. | Yes | [View Details](rules/IR-column-layout.md) |
| [`IR-blank-lines`](rules/IR-blank-lines.md) | Limit consecutive blank lines to a maximum of one. | Yes | [View Details](rules/IR-blank-lines.md) |
| [`IR-paren-single`](rules/IR-paren-single.md) | Unnecessary parentheses around a single condition should be removed. | Yes | [View Details](rules/IR-paren-single.md) |
| [`IR-function-case`](rules/IR-function-case.md) | Function names should be the same case (default lowercase). | Yes | [View Details](rules/IR-function-case.md) |
| [`IR-paren-same-op`](rules/IR-paren-same-op.md) | Unnecessary parentheses around homogeneous logical conditions should be removed. | Yes | [View Details](rules/IR-paren-same-op.md) |
| [`IR-is-null-space`](rules/IR-is-null-space.md) | Standardize spacing for null predicates (ISNULL -> IS NULL, ISNOTNULL -> IS NOT NULL). | Yes | [View Details](rules/IR-is-null-space.md) |

## Function / Procedure Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| *No rules active* | *Future function/procedure rules will be listed here* | - | - |

## Insert / Update / Delete Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| *No rules active* | *Future insert/update/delete rules will be listed here* | - | - |
