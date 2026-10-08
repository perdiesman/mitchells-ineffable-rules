# MIR Agent Guidance

## Scope and routing

- This file applies to the full repository. More specific `AGENTS.md` files add guidance for their directories.
- Engine work follows `mir/engine/AGENTS.md`; language rules follow `mir/rules/AGENTS.md`; tests and generated documentation have their own guides.
- Keep Java work out of scope unless the user explicitly requests it. Current priority is SQL, XML, MyBatis, and Trellis.

## Architecture and compatibility

- Preserve the dynamic rule architecture. Built-in and external rules must continue to implement `BaseRule` and load through the same validated loader.
- Keep configuration backward compatible unless a documented versioned change is intentional. New commit-oriented behavior should be opt-in.
- Treat Web, AERIE, EAGLE-AI, and PyGarden as compatibility inputs, not as repositories owned by this project.
- Store local compatibility clones and generated benchmark artifacts under ignored `local/`; never commit them.
- Do not publish packages or push branches unless the user explicitly requests it.

## Workflow

- Work in small, independently revertible commits after focused checks pass.
- Preserve user changes and inspect repository status before every commit.
- Update the README and relevant generated rule documentation when behavior or interfaces change.
- Track cumulative development time through the repository hook and README workflow.

## Verification

- Run the complete unit suite before final handoff.
- Verify fixers are idempotent and do not modify content outside their authorized scope.
- Run `git diff --check`, generated-documentation drift checks, and representative compatibility benchmarks.
