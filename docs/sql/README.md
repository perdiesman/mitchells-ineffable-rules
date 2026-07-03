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
| [`IR-keyword-case`](rules/IR-keyword-case.md) | SQL keywords must be in uppercase. | Yes | [View Details](rules/IR-keyword-case.md) |
| [`IR-indent`](rules/IR-indent.md) | Indent should be equal amounts of spaces (default 4). | Yes | [View Details](rules/IR-indent.md) |

## Select / View / Materialized View Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-create-view-indent`](rules/IR-create-view-indent.md) | SELECT statements under a CREATE VIEW should be indented 4 spaces relative to the CREATE VIEW statement. | Yes | [View Details](rules/IR-create-view-indent.md) |
| [`IR-subquery-compact`](rules/IR-subquery-compact.md) | Multiline subquery sources inside FROM or JOIN clauses should be compacted to a single line if they fit within 140 characters. | Yes | [View Details](rules/IR-subquery-compact.md) |
| [`IR-null-coalesce`](rules/IR-null-coalesce.md) | Standardize nullable equality predicates to COALESCE(x, -1) form. | Yes | [View Details](rules/IR-null-coalesce.md) |
| [`IR-empty-command`](rules/IR-empty-command.md) | Remove empty SQL commands, such as duplicate semicolons or leading semicolons. | Yes | [View Details](rules/IR-empty-command.md) |
| [`IR-table-alias-as`](rules/IR-table-alias-as.md) | Table and subquery aliases should not use the AS keyword. | Yes | [View Details](rules/IR-table-alias-as.md) |
| [`IR-from-multi`](rules/IR-from-multi.md) | Multi-table or JOINed FROM entries should be formatted with one entry per line, indented at 4 spaces. | Yes | [View Details](rules/IR-from-multi.md) |
| [`IR-operator-spacing`](rules/IR-operator-spacing.md) | Operators should have a single space on both sides. | Yes | [View Details](rules/IR-operator-spacing.md) |
| [`IR-subquery-indent`](rules/IR-subquery-indent.md) | Subqueries should be indented 4 spaces relative to their opening parenthesis. | Yes | [View Details](rules/IR-subquery-indent.md) |
| [`IR-where-single`](rules/IR-where-single.md) | Single WHERE condition should be on the same line as the WHERE keyword. | Yes | [View Details](rules/IR-where-single.md) |
| [`IR-join-parens`](rules/IR-join-parens.md) | Unnecessary parentheses around a JOIN clause should be removed. | Yes | [View Details](rules/IR-join-parens.md) |
| [`IR-from-single`](rules/IR-from-single.md) | Single FROM entry should be on the same line as the FROM keyword. | Yes | [View Details](rules/IR-from-single.md) |
| [`IR-alias-as`](rules/IR-alias-as.md) | Column aliases must use the AS keyword. | Yes | [View Details](rules/IR-alias-as.md) |
| [`IR-clause-alignment`](rules/IR-clause-alignment.md) | Main query clause keywords (SELECT, FROM, WHERE, GROUP BY, HAVING, ORDER BY, LIMIT) must have the exact same indentation within the same query block when the query spans multiple lines. | Yes | [View Details](rules/IR-clause-alignment.md) |
| [`IR-column-layout`](rules/IR-column-layout.md) | On select, order by, group by, if all the columns fit on one line then put them on one line, otherwise wrap one per line. | Yes | [View Details](rules/IR-column-layout.md) |
| [`IR-blank-lines`](rules/IR-blank-lines.md) | Limit consecutive blank lines to a configurable maximum. | Yes | [View Details](rules/IR-blank-lines.md) |
| [`IR-cte-format`](rules/IR-cte-format.md) | Format layout of CTE WITH blocks: align subquery aliases, parenthesis and the final query block. | Yes | [View Details](rules/IR-cte-format.md) |
| [`IR-paren-single`](rules/IR-paren-single.md) | Unnecessary parentheses around a single condition should be removed. | Yes | [View Details](rules/IR-paren-single.md) |
| [`IR-in-exists`](rules/IR-in-exists.md) | EXISTS is preferred over IN with a subquery. | No | [View Details](rules/IR-in-exists.md) |
| [`IR-function-case`](rules/IR-function-case.md) | Function names should be the same case (default lowercase). | Yes | [View Details](rules/IR-function-case.md) |
| [`IR-join-on-multi`](rules/IR-join-on-multi.md) | Split AND or OR conditions in JOIN ON clauses to separate lines, indented 4 spaces. | Yes | [View Details](rules/IR-join-on-multi.md) |
| [`IR-paren-same-op`](rules/IR-paren-same-op.md) | Unnecessary parentheses around homogeneous logical conditions should be removed. | Yes | [View Details](rules/IR-paren-same-op.md) |
| [`IR-paren-content-indent`](rules/IR-paren-content-indent.md) | Content inside multi-line parentheses should be indented 4 spaces relative to the opening parenthesis, and the closing parenthesis should align with it. | Yes | [View Details](rules/IR-paren-content-indent.md) |
| [`IR-where-multi`](rules/IR-where-multi.md) | Each AND/OR clause in a multi-condition WHERE clause should start on its own line, indented at 4 spaces. | Yes | [View Details](rules/IR-where-multi.md) |
| [`IR-case`](rules/IR-case.md) | CASE statements should be formatted with WHEN/THEN on separate lines unless the block is simple (exactly one WHEN condition and an optional ELSE clause) and fits on a single line within length constraints. | Yes | [View Details](rules/IR-case.md) |

## Function / Procedure Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| *No rules active* | *Future function/procedure rules will be listed here* | - | - |

## Insert / Update / Delete Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| *No rules active* | *Future insert/update/delete rules will be listed here* | - | - |
