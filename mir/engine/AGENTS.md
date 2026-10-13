# Engine Guidance

- Keep file, stdin, raw-content, and staged-Git inputs on one document-processing path.
- Selection scopes are immutable per document. Never store or expand changed lines globally across files.
- Preserve partially staged and unstaged Git content. Index updates must not silently stage unrelated working-tree edits.
- Surface rule crashes, unsafe edits, and non-convergence as explicit diagnostics. Do not silently swallow engine failures.
- Cache parsing only by content and configuration identity; do not retain unbounded caches keyed by object identity.
- Add focused tests for public CLI/configuration changes and failure behavior.
