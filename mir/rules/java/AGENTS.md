# Java Rule Guidance

- Parse Java through `java_utils.parse_java`; do not add rule-local structural regular expressions.
- Preserve non-whitespace tokens, comments, string and character literals, and text-block contents in commit-profile fixes.
- Keep four-space block and continuation indentation and a 120-column default configurable through rule metadata.
- Structural edits must be wholly contained in authorized lines and must not cross rule-disable regions.
- Treat generated files as compatibility inputs controlled by the language configuration, not as formatter fixtures.
- Examples and typed cases must use generic packages, types, methods, and values.
- Rules that need compiler symbol resolution must report conservatively or remain out of scope for the syntax-only ruleset.
