# Test Guidance

- Tests import rule metadata as the source of truth for accepted, reported, fixed, and idempotent behavior.
- Keep compatibility fixtures small, anonymized, deterministic, and independent of sibling repositories or network access.
- Git integration tests use temporary repositories and configure their own identity and hooks.
- Performance assertions should validate bounded work or compare broad regression budgets; avoid fragile millisecond thresholds in the unit suite.
- Never weaken an assertion merely to accept an unsafe formatter result.
