# CLAUDE.md

## Project Overview

<!-- 2-3 sentences. What does this project do, who uses it, what's the tech stack. -->

## Project Status

<!-- Current phase, what's in progress, what's next.
     Example: "Phase 0 (validation) — in progress. See docs/plans/..." -->

## Development Workflow

This project uses **spec-driven development**. See `SPEC-WORKFLOW.md` for the full workflow, templates, and governing rules. Key points:

- Every file is owned by exactly one spec (tracked in `docs/REGISTER.md`)
- Shared data structures live in `docs/definitions/` (versioned: v0 while draft, v1+ when stable)
- Version pins tracked in `contracts.yaml` and enforced by contract tests
- Tests are tiered: unit (always) → contract (when applicable) → integration (when applicable)
- Collaborative authoring: human writes Purpose/Behaviour, Claude fills boilerplate
- Draft-mode: during early development, note ambiguities and continue rather than stopping

## Testing Workflow

This project uses **test-driven development** (TDD). When implementing code changes, follow the red-green-refactor cycle:

1. **Red:** Write a failing test that captures the expected behaviour. If you can't write the test, the spec is underspecified — surface the ambiguity before writing code.
2. **Green:** Write the minimum code to make the test pass.
3. **Refactor:** Clean up while keeping tests green.

### When TDD applies

- All code changes that add or modify behaviour
- Bug fixes (write a test that reproduces the bug first)
- Refactoring that changes interfaces (tests prove equivalence)

### When TDD does not apply

- Documentation-only changes (markdown, comments)
- Configuration changes (YAML, JSON) with no runtime behaviour
- Exploratory spikes (throwaway code in `spikes/`)

### Test tiers

Tests are tiered and run in order. A failure at any tier blocks the next:

1. **Unit tests** (always) — isolated, mocked dependencies
2. **Contract tests** (when applicable) — verify conformance to shared definitions
3. **Integration tests** (when applicable) — cross-component interaction

Declare "N/A — [reason]" for inapplicable tiers; never silently omit.

### Plan requirements

Every implementation plan that proposes code changes must include a **Tests** section specifying what will be tested and at which tier. No Tests section means no implementation. If there is genuinely nothing to test, say why explicitly.

## Git Workflow

- **Branch protection:** Never commit directly to `main`. All work happens on feature branches with prefixes: `feat/`, `fix/`, `docs/`, `chore/`.
- **Explicit staging:** Stage files by name. Never use `git add -A` or `git add .`.
- **Commit messages:** Explain *why*, not *what* — the diff shows what changed. Reference GitHub issues where applicable (e.g., "Part of #8", "Closes #12").
- **One logical change per commit.** Don't bundle unrelated changes.
- **Pull requests:** Use `/pr` to create pull requests. It runs a health-check summary and pushes automatically.
- **Security review:** Run `/security-review` before PRs that modify hooks, skills, or agent-facing code.
- **Post-merge cleanup:** After a PR merges, switch to main, pull, and delete the local feature branch.
- **Skill naming:** Skills prefixed with `dev-` are project-internal and not distributed to downstream projects by `/init-project`.

## Key Documents

### Governed documents (spec workflow)

| Document | Location | Status |
|---|---|---|
| **Workflow** | `SPEC-WORKFLOW.md` | Active |
| **Architecture** | `docs/ARCHITECTURE.md` | <!-- draft / active / not yet created --> |
| **Register** | `docs/REGISTER.md` | <!-- draft / active / not yet created --> |
| **Version pins** | `contracts.yaml` | <!-- draft / active / not yet created --> |
| **Definitions** | `docs/definitions/` | <!-- count and status --> |
| **Specs** | `docs/specs/*.spec.md` | <!-- count and status --> |

### Reference documents

| Document | Location |
|---|---|

### Plans (ephemeral, not governed)

| Document | Location |
|---|---|

## Package Structure

```
<!-- Project directory layout. Update as structure evolves. -->
```

## Running Tests

```bash
<!-- Primary test command -->
```

See **Testing Workflow** above for the TDD process and tier ordering.

## Key Design Decisions

<!-- Bullet list of the most important architectural decisions.
     These should also appear in ARCHITECTURE.md's Decisions table,
     but are repeated here for quick orientation. -->

## Environment

<!-- Runtime requirements, external dependencies, setup instructions.
     Example: "Requires Python 3.10+, Databricks for integration tests" -->
