# JAVA Style Guide & Rules

This document describes all JAVA linting rules supported by Mitchell's Ineffable Rules (IR) Linter.

## Categories

- [General Rules](#general-rules)
- [Source Structure](#source-structure)
- [Imports](#imports)
- [Whitespace and Layout](#whitespace-and-layout)
- [Classes and Interfaces](#classes-and-interfaces)
- [Method Declarations](#method-declarations)
- [Variables and Fields](#variables-and-fields)
- [Expressions](#expressions)
- [Control Flow](#control-flow)
- [Naming](#naming)
- [Documentation](#documentation)
- [Correctness](#correctness)

## General Rules

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-final-newline`](rules/general/IR-final-newline.md) | Java files end with exactly one line terminator. | Yes | [View Details](rules/general/IR-final-newline.md) |
| [`IR-java-syntax`](rules/general/IR-java-syntax.md) | Java source must parse without missing or erroneous syntax nodes. | No | [View Details](rules/general/IR-java-syntax.md) |
| [`IR-line-length`](rules/general/IR-line-length.md) | Java code should not exceed the configured line length; package, import, and text-block payload lines are exempt. | No | [View Details](rules/general/IR-line-length.md) |
| [`IR-long-literal-suffix`](rules/general/IR-long-literal-suffix.md) | Use an uppercase L suffix for long integer literals. | Sometimes | [View Details](rules/general/IR-long-literal-suffix.md) |

## Source Structure

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-annotation-layout`](rules/source-structure/IR-annotation-layout.md) | Place declaration annotations on separate lines before modifiers and declarations. | Yes | [View Details](rules/source-structure/IR-annotation-layout.md) |
| [`IR-modifier-order`](rules/source-structure/IR-modifier-order.md) | Use the standard Java modifier order. | Yes | [View Details](rules/source-structure/IR-modifier-order.md) |
| [`IR-one-top-level-type`](rules/source-structure/IR-one-top-level-type.md) | Keep one top-level Java type per ordinary source file and match its filename. | No | [View Details](rules/source-structure/IR-one-top-level-type.md) |
| [`IR-source-layout`](rules/source-structure/IR-source-layout.md) | Separate package, import, and top-level type sections with one blank line. | Sometimes | [View Details](rules/source-structure/IR-source-layout.md) |
| [`IR-type-clause-layout`](rules/source-structure/IR-type-clause-layout.md) | Keep fitting implements, permits, and throws clauses compact; otherwise list one type per line. | Yes | [View Details](rules/source-structure/IR-type-clause-layout.md) |

## Imports

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-import-order`](rules/imports/IR-import-order.md) | Sort imports into static, platform, third-party, and project groups. | Sometimes | [View Details](rules/imports/IR-import-order.md) |
| [`IR-no-wildcard-imports`](rules/imports/IR-no-wildcard-imports.md) | Use explicit imports instead of wildcard imports. | No | [View Details](rules/imports/IR-no-wildcard-imports.md) |
| [`IR-redundant-imports`](rules/imports/IR-redundant-imports.md) | Remove duplicate, java.lang, and same-package imports. | Sometimes | [View Details](rules/imports/IR-redundant-imports.md) |

## Whitespace and Layout

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-blank-lines`](rules/whitespace/layout/IR-blank-lines.md) | Do not start a Java file with a blank line or use consecutive blank lines. | Yes | [View Details](rules/whitespace/layout/IR-blank-lines.md) |
| [`IR-brace-layout`](rules/whitespace/layout/IR-brace-layout.md) | Use K&R brace layout, multiline nonempty blocks, and joined else/catch/finally clauses. | Yes | [View Details](rules/whitespace/layout/IR-brace-layout.md) |
| [`IR-empty-body-layout`](rules/whitespace/layout/IR-empty-body-layout.md) | Write empty Java declaration and executable bodies as compact braces. | Yes | [View Details](rules/whitespace/layout/IR-empty-body-layout.md) |
| [`IR-indent`](rules/whitespace/layout/IR-indent.md) | Indent Java blocks and continuations with configurable four-space levels. | Yes | [View Details](rules/whitespace/layout/IR-indent.md) |
| [`IR-one-statement-line`](rules/whitespace/layout/IR-one-statement-line.md) | Place each Java statement on its own line. | Yes | [View Details](rules/whitespace/layout/IR-one-statement-line.md) |
| [`IR-spacing`](rules/whitespace/layout/IR-spacing.md) | Use canonical spaces around Java operators, separators, and control parentheses. | Yes | [View Details](rules/whitespace/layout/IR-spacing.md) |
| [`IR-whitespace`](rules/whitespace/layout/IR-whitespace.md) | Use spaces for indentation and remove trailing whitespace outside literals and comments. | Yes | [View Details](rules/whitespace/layout/IR-whitespace.md) |

## Classes and Interfaces

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-enum-layout`](rules/classes/interfaces/IR-enum-layout.md) | Keep fitting enum constants together; otherwise place each constant on its own line. | Yes | [View Details](rules/classes/interfaces/IR-enum-layout.md) |
| [`IR-member-spacing`](rules/classes/interfaces/IR-member-spacing.md) | Group adjacent fields and separate constructors, methods, initializers, and nested types with one blank line. | Yes | [View Details](rules/classes/interfaces/IR-member-spacing.md) |
| [`IR-type-parameter-layout`](rules/classes/interfaces/IR-type-parameter-layout.md) | Keep fitting generic type parameters compact; otherwise place each parameter on its own line. | Yes | [View Details](rules/classes/interfaces/IR-type-parameter-layout.md) |

## Method Declarations

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-argument-layout`](rules/methods/IR-argument-layout.md) | Keep fitting Java argument and parameter lists compact; otherwise place each item on its own line. | Yes | [View Details](rules/methods/IR-argument-layout.md) |
| [`IR-overload-grouping`](rules/methods/IR-overload-grouping.md) | Keep methods and constructors with the same name in contiguous groups. | No | [View Details](rules/methods/IR-overload-grouping.md) |
| [`IR-parameter-annotation-layout`](rules/methods/IR-parameter-annotation-layout.md) | Keep fitting parameter annotations compact; otherwise place each annotation and the declared type on its own line. | Yes | [View Details](rules/methods/IR-parameter-annotation-layout.md) |
| [`IR-parameter-layout`](rules/methods/IR-parameter-layout.md) | Keep fitting method, constructor, lambda, and record parameters compact; otherwise use one parameter per line. | Yes | [View Details](rules/methods/IR-parameter-layout.md) |

## Variables and Fields

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-array-initializer-layout`](rules/variables/IR-array-initializer-layout.md) | Keep fitting array initializers compact; otherwise place each value on its own line. | Yes | [View Details](rules/variables/IR-array-initializer-layout.md) |
| [`IR-array-type-style`](rules/variables/IR-array-type-style.md) | Attach array brackets to the type rather than the variable name. | No | [View Details](rules/variables/IR-array-type-style.md) |
| [`IR-one-variable-declaration`](rules/variables/IR-one-variable-declaration.md) | Declare one field or local variable per declaration outside for-loop headers. | No | [View Details](rules/variables/IR-one-variable-declaration.md) |

## Expressions

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-chain-layout`](rules/expressions/IR-chain-layout.md) | Keep fitting method chains compact; otherwise align each chained call one continuation level in. | Yes | [View Details](rules/expressions/IR-chain-layout.md) |
| [`IR-expression-layout`](rules/expressions/IR-expression-layout.md) | Keep fitting binary expressions compact; align wrapped operators at one continuation level. | Yes | [View Details](rules/expressions/IR-expression-layout.md) |
| [`IR-lambda-layout`](rules/expressions/IR-lambda-layout.md) | Keep fitting lambda expressions compact and indent wrapped expression bodies after the arrow. | Yes | [View Details](rules/expressions/IR-lambda-layout.md) |
| [`IR-redundant-boolean-comparison`](rules/expressions/IR-redundant-boolean-comparison.md) | Avoid explicit comparisons with true or false when the boolean expression is clear. | Sometimes | [View Details](rules/expressions/IR-redundant-boolean-comparison.md) |
| [`IR-ternary-layout`](rules/expressions/IR-ternary-layout.md) | Keep fitting ternary expressions compact; otherwise align question and colon branches. | Yes | [View Details](rules/expressions/IR-ternary-layout.md) |

## Control Flow

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-loop-header-layout`](rules/control-flow/IR-loop-header-layout.md) | Keep fitting for-loop headers compact; otherwise place each logical header part on its own line. | Yes | [View Details](rules/control-flow/IR-loop-header-layout.md) |
| [`IR-required-braces`](rules/control-flow/IR-required-braces.md) | Use braces for if, else, for, while, and do bodies. | Sometimes | [View Details](rules/control-flow/IR-required-braces.md) |
| [`IR-switch-fallthrough`](rules/control-flow/IR-switch-fallthrough.md) | Mark intentional fall-through in colon-style switch statement groups. | No | [View Details](rules/control-flow/IR-switch-fallthrough.md) |
| [`IR-switch-layout`](rules/control-flow/IR-switch-layout.md) | Place switch cases and colon-style case statements on readable, consistently indented lines. | Yes | [View Details](rules/control-flow/IR-switch-layout.md) |
| [`IR-try-resource-layout`](rules/control-flow/IR-try-resource-layout.md) | Keep fitting try resources compact; otherwise place each resource on its own line. | Yes | [View Details](rules/control-flow/IR-try-resource-layout.md) |

## Naming

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-constant-name`](rules/naming/IR-constant-name.md) | Use UPPER_SNAKE_CASE for configured static-final constant declarations. | No | [View Details](rules/naming/IR-constant-name.md) |
| [`IR-method-name`](rules/naming/IR-method-name.md) | Use lowerCamelCase Java method names. | No | [View Details](rules/naming/IR-method-name.md) |
| [`IR-package-name`](rules/naming/IR-package-name.md) | Use lowercase alphanumeric Java package components. | No | [View Details](rules/naming/IR-package-name.md) |
| [`IR-type-name`](rules/naming/IR-type-name.md) | Use UpperCamelCase Java type names. | No | [View Details](rules/naming/IR-type-name.md) |
| [`IR-variable-name`](rules/naming/IR-variable-name.md) | Use lowerCamelCase for Java fields, parameters, and local variables. | No | [View Details](rules/naming/IR-variable-name.md) |

## Documentation

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-disabled-test-reason`](rules/documentation/IR-disabled-test-reason.md) | Give disabled JUnit tests a nonempty reason. | No | [View Details](rules/documentation/IR-disabled-test-reason.md) |
| [`IR-javadoc-completeness`](rules/documentation/IR-javadoc-completeness.md) | Keep existing public API Javadoc tags synchronized with method parameters, returns, and throws clauses. | No | [View Details](rules/documentation/IR-javadoc-completeness.md) |
| [`IR-javadoc-placement`](rules/documentation/IR-javadoc-placement.md) | Place Javadoc before declaration annotations. | No | [View Details](rules/documentation/IR-javadoc-placement.md) |
| [`IR-javadoc-tags`](rules/documentation/IR-javadoc-tags.md) | Use canonical Javadoc block-tag order and nonempty descriptions. | No | [View Details](rules/documentation/IR-javadoc-tags.md) |
| [`IR-public-api-javadoc`](rules/documentation/IR-public-api-javadoc.md) | Document public and protected top-level types and members. | No | [View Details](rules/documentation/IR-public-api-javadoc.md) |

## Correctness

| Rule Name | Short Description | Fixable | Details |
| :--- | :--- | :---: | :---: |
| [`IR-assignment-in-condition`](rules/correctness/IR-assignment-in-condition.md) | Avoid assignments inside control-flow conditions. | No | [View Details](rules/correctness/IR-assignment-in-condition.md) |
| [`IR-console-output`](rules/correctness/IR-console-output.md) | Use project logging instead of console output or printStackTrace. | No | [View Details](rules/correctness/IR-console-output.md) |
| [`IR-empty-catch`](rules/correctness/IR-empty-catch.md) | Explain or handle intentionally ignored exceptions. | No | [View Details](rules/correctness/IR-empty-catch.md) |
| [`IR-empty-statement`](rules/correctness/IR-empty-statement.md) | Do not use an accidental empty statement as a control-flow body. | No | [View Details](rules/correctness/IR-empty-statement.md) |
| [`IR-equals-hash-code`](rules/correctness/IR-equals-hash-code.md) | Declare equals and hashCode together in concrete Java classes. | No | [View Details](rules/correctness/IR-equals-hash-code.md) |
| [`IR-finally-control-flow`](rules/correctness/IR-finally-control-flow.md) | Do not abruptly return, throw, break, or continue from a finally block. | No | [View Details](rules/correctness/IR-finally-control-flow.md) |
| [`IR-forbidden-api`](rules/correctness/IR-forbidden-api.md) | Report explicitly configured Java imports, qualified references, and invocations. | No | [View Details](rules/correctness/IR-forbidden-api.md) |
| [`IR-interrupted-exception`](rules/correctness/IR-interrupted-exception.md) | Propagate InterruptedException or visibly restore the thread interruption flag. | No | [View Details](rules/correctness/IR-interrupted-exception.md) |
