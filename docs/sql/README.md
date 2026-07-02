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
| [`IR-column-layout`](rules/IR-column-layout.md) | On select, order by, group by, if all the columns fit on one line then put them on one line, otherwise wrap one per line. | Yes | [View Details](rules/IR-column-layout.md) |
| [`IR-function-case`](rules/IR-function-case.md) | Function names should be the same case (default lowercase). | Yes | [View Details](rules/IR-function-case.md) |

## Function / Procedure Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| *No rules active* | *Future function/procedure rules will be listed here* | - | - |

## Insert / Update / Delete Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| *No rules active* | *Future insert/update/delete rules will be listed here* | - | - |
