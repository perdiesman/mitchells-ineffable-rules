# SQL Style Guide & Rules

This document describes all SQL linting rules supported by Mitchell's Ineffable Rules (IR) Linter.

## Categories

- [General Rules](#general-rules)
- [Query Structure Rules](#query-structure-rules)
- [Schema Definition Rules](#schema-definition-rules)
- [Data Modification Rules](#data-modification-rules)
- [Routine & Procedure Rules](#routine-procedure-rules)

## General Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-operator-spacing`](rules/general/IR-operator-spacing.md) | Operators should have a single space on both sides. | Yes | [View Details](rules/general/IR-operator-spacing.md) |
| [`IR-redundant-keywords`](rules/general/IR-redundant-keywords.md) | Remove redundant implied keywords like INNER, OUTER, and ASC. | Yes | [View Details](rules/general/IR-redundant-keywords.md) |
| [`IR-trailing-semicolon`](rules/general/IR-trailing-semicolon.md) | Enforce that the last SQL statement ends with a trailing semicolon, placed immediately after the statement text. | Yes | [View Details](rules/general/IR-trailing-semicolon.md) |
| [`IR-comment-spacing`](rules/general/IR-comment-spacing.md) | Enforce a single space after the double-dash comment prefix. | Yes | [View Details](rules/general/IR-comment-spacing.md) |
| [`IR-eof-newline`](rules/general/IR-eof-newline.md) | Enforce that every SQL file ends with exactly one newline character. | Yes | [View Details](rules/general/IR-eof-newline.md) |
| [`IR-line-length`](rules/general/IR-line-length.md) | Lines must not exceed the configured maximum length. | No | [View Details](rules/general/IR-line-length.md) |
| [`IR-blank-lines`](rules/general/IR-blank-lines.md) | Limit consecutive blank lines to a configurable maximum. | Yes | [View Details](rules/general/IR-blank-lines.md) |
| [`IR-function-case`](rules/general/IR-function-case.md) | Function names should be the same case (default lowercase). | Yes | [View Details](rules/general/IR-function-case.md) |
| [`IR-keyword-case`](rules/general/IR-keyword-case.md) | SQL keywords must be in uppercase. | Yes | [View Details](rules/general/IR-keyword-case.md) |
| [`IR-indent`](rules/general/IR-indent.md) | Indent should be equal amounts of spaces (default 4). | Yes | [View Details](rules/general/IR-indent.md) |

## Query Structure Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-subquery-compact`](rules/queries/IR-subquery-compact.md) | Multiline subquery sources inside FROM or JOIN clauses should be compacted to a single line if they fit within 140 characters. | Yes | [View Details](rules/queries/IR-subquery-compact.md) |
| [`IR-null-coalesce`](rules/queries/IR-null-coalesce.md) | Standardize nullable equality predicates to COALESCE(x, -1) form. | Yes | [View Details](rules/queries/IR-null-coalesce.md) |
| [`IR-empty-command`](rules/queries/IR-empty-command.md) | Remove empty SQL commands, such as duplicate semicolons or leading semicolons. | Yes | [View Details](rules/queries/IR-empty-command.md) |
| [`IR-table-alias-as`](rules/queries/IR-table-alias-as.md) | Table and subquery aliases should not use the AS keyword. | Yes | [View Details](rules/queries/IR-table-alias-as.md) |
| [`IR-from-multi`](rules/queries/IR-from-multi.md) | Multi-table or JOINed FROM entries should be formatted with one entry per line, indented at 4 spaces. | Yes | [View Details](rules/queries/IR-from-multi.md) |
| [`IR-count-star`](rules/queries/IR-count-star.md) | Standardize COUNT(1) or row-counting expressions to COUNT(*). | Yes | [View Details](rules/queries/IR-count-star.md) |
| [`IR-subquery-indent`](rules/queries/IR-subquery-indent.md) | Subqueries should be indented 4 spaces relative to their opening parenthesis. | Yes | [View Details](rules/queries/IR-subquery-indent.md) |
| [`IR-where-single`](rules/queries/IR-where-single.md) | Single WHERE condition should be on the same line as the WHERE keyword. | Yes | [View Details](rules/queries/IR-where-single.md) |
| [`IR-join-parens`](rules/queries/IR-join-parens.md) | Unnecessary parentheses around a JOIN clause should be removed. | Yes | [View Details](rules/queries/IR-join-parens.md) |
| [`IR-from-paren-layout`](rules/queries/IR-from-paren-layout.md) | Parenthesized column alias lists in FROM/JOIN clauses should format entries one per line if the line exceeds max length. | Yes | [View Details](rules/queries/IR-from-paren-layout.md) |
| [`IR-from-single`](rules/queries/IR-from-single.md) | Single FROM entry should be on the same line as the FROM keyword. | Yes | [View Details](rules/queries/IR-from-single.md) |
| [`IR-is-null`](rules/queries/IR-is-null.md) | Standardize NULL comparison predicates to use IS NULL and IS NOT NULL operators. | Yes | [View Details](rules/queries/IR-is-null.md) |
| [`IR-distinct-parentheses`](rules/queries/IR-distinct-parentheses.md) | Remove redundant parentheses around DISTINCT arguments, preserving DISTINCT ON (col) syntax. | Yes | [View Details](rules/queries/IR-distinct-parentheses.md) |
| [`IR-expression-split`](rules/queries/IR-expression-split.md) | Long lines should split on function/expression parentheses, and optionally on additive/logical operators if still too long. | Yes | [View Details](rules/queries/IR-expression-split.md) |
| [`IR-between`](rules/queries/IR-between.md) | Standardize range predicate check of form 'a >= b AND a <= c' to 'a BETWEEN b AND c'. | Yes | [View Details](rules/queries/IR-between.md) |
| [`IR-subquery-depth-limit`](rules/queries/IR-subquery-depth-limit.md) | Subquery nesting depth should not exceed the configured limit (default: 3). When over the limit, Common Table Expressions (CTEs) are preferred. | No | [View Details](rules/queries/IR-subquery-depth-limit.md) |
| [`IR-boolean-comparison`](rules/queries/IR-boolean-comparison.md) | Standardize boolean comparison predicates to use idiomatic boolean predicates. | Yes | [View Details](rules/queries/IR-boolean-comparison.md) |
| [`IR-alias-as`](rules/queries/IR-alias-as.md) | Column aliases must use the AS keyword. | Yes | [View Details](rules/queries/IR-alias-as.md) |
| [`IR-clause-alignment`](rules/queries/IR-clause-alignment.md) | Main query clause keywords (SELECT, FROM, WHERE, GROUP BY, HAVING, ORDER BY, LIMIT) must have the exact same indentation within the same query block when the query spans multiple lines. | Yes | [View Details](rules/queries/IR-clause-alignment.md) |
| [`IR-column-layout`](rules/queries/IR-column-layout.md) | On select, order by, group by, if all the columns fit on one line then put them on one line, otherwise wrap one per line. | Yes | [View Details](rules/queries/IR-column-layout.md) |
| [`IR-paren-multi`](rules/queries/IR-paren-multi.md) | Parentheses wrapping multiple logical conditions in WHERE/ON clauses must format contents on separate lines, indented 4 spaces. | Yes | [View Details](rules/queries/IR-paren-multi.md) |
| [`IR-cte-format`](rules/queries/IR-cte-format.md) | Format layout of CTE WITH blocks: align subquery aliases, parenthesis and the final query block. | Yes | [View Details](rules/queries/IR-cte-format.md) |
| [`IR-paren-single`](rules/queries/IR-paren-single.md) | Unnecessary parentheses around a single condition should be removed. | Yes | [View Details](rules/queries/IR-paren-single.md) |
| [`IR-in-exists`](rules/queries/IR-in-exists.md) | EXISTS is preferred over IN with a subquery. | No | [View Details](rules/queries/IR-in-exists.md) |
| [`IR-join-on-multi`](rules/queries/IR-join-on-multi.md) | Split AND or OR conditions in JOIN ON clauses to separate lines, indented 4 spaces. | Yes | [View Details](rules/queries/IR-join-on-multi.md) |
| [`IR-paren-same-op`](rules/queries/IR-paren-same-op.md) | Unnecessary parentheses around homogeneous logical conditions should be removed. | Yes | [View Details](rules/queries/IR-paren-same-op.md) |
| [`IR-paren-content-indent`](rules/queries/IR-paren-content-indent.md) | Content inside multi-line parentheses should be indented 4 spaces relative to the opening parenthesis, and the closing parenthesis should align with it. | Yes | [View Details](rules/queries/IR-paren-content-indent.md) |
| [`IR-where-multi`](rules/queries/IR-where-multi.md) | Each AND/OR clause in a multi-condition WHERE clause should start on its own line, indented at 4 spaces. | Yes | [View Details](rules/queries/IR-where-multi.md) |
| [`IR-case`](rules/queries/IR-case.md) | CASE statements should be formatted with WHEN/THEN on separate lines unless the block is simple (exactly one WHEN condition and an optional ELSE clause) and fits on a single line within length constraints. | Yes | [View Details](rules/queries/IR-case.md) |

## Schema Definition Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-create-view-indent`](rules/schema-definition/IR-create-view-indent.md) | SELECT statements under a CREATE VIEW should be indented 4 spaces relative to the CREATE VIEW statement. | Yes | [View Details](rules/schema-definition/IR-create-view-indent.md) |

## Data Modification Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| *No rules active* | *Future data-modification rules will be listed here* | - | - |

## Routine & Procedure Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| *No rules active* | *Future routines rules will be listed here* | - | - |
