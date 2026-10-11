# Java Test Guidance

- Use generic fixtures only; never copy names, packages, or implementation details from compatibility repositories.
- Cover Java 8-era syntax and modern records, sealed types, text blocks, switch expressions, and pattern matching.
- Every fixer test must assert exact output, clean-after-fix behavior, idempotency, and preservation of literals/comments.
- Exercise one-line, block, `IR-all`, and formatter suppression directives, including directive-like text inside literals.
- Staged-selection tests must prove edits stay within the smallest authorized Java construct.
