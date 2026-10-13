# Documentation Guidance

- Rule catalogs under `docs/<language>/` are generated from rule metadata. Do not hand-edit generated rule pages.
- `docs/custom_rules.md`, `docs/publishing.md`, and other workflow guides are maintained by hand.
- Regenerate documentation with the project generator and verify that a second generation produces no diff.
- Keep examples synchronized with the cases exercised by meta-tests.
