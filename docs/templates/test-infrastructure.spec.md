# Test Infrastructure

## Status
draft

## Owner
<!-- Who is responsible for this spec's correctness and currency. -->

## Target Phase
Phase 0

## Purpose

Define the test framework, runner configuration, directory layout, and shared utilities that all other specs' tests depend on. This is one of two reserved specs (see SPEC-WORKFLOW.md §5) and must be created before any feature specs are implemented.

## Requires (Inbound Contracts)

| Dependency | Source | Definition |
|------------|--------|------------|
| — | — | No inbound contracts — this is a foundational spec |

## Provides (Outbound Contracts)

| Export | Type | Definition |
|--------|------|------------|
| Test runner | Tool | inline — <!-- e.g. pytest, jest, bats-core, go test --> installed and configured |
| Test helper library | Library | inline — `tests/helpers/` or equivalent with common fixtures and assertions |
| Test directory structure | Convention | inline — `tests/unit/`, `tests/contract/`, `tests/integration/` |
| Test entry point | Command | inline — single command that runs all tiers in order |

## Behaviour

### Test Framework

<!-- Choose the test framework appropriate for your project's language/stack.
     Record the choice and rationale in the Decisions table below.

     Examples:
     - Python: pytest with pytest-cov
     - JavaScript/TypeScript: jest or vitest
     - Bash: bats-core with bats-assert
     - Go: go test with testify
     - Rust: cargo test
     - Multi-language: one framework per language, unified entry point -->

### Test Directory Layout

<!-- Define the directory structure. The tier layout must follow the convention
     in SPEC-WORKFLOW.md §6. Adapt the subdirectory naming to your stack.

     Standard layout:
     tests/
     ├── unit/           # Tier 1: isolated, mocked dependencies
     ├── contract/       # Tier 2: verify conformance to shared definitions
     ├── integration/    # Tier 3: cross-spec interaction
     ├── helpers/        # Shared fixtures, factories, utilities
     └── fixtures/       # Test data, sample files, golden outputs
-->

### Test Entry Point

<!-- Define a single command that runs all applicable tiers in order,
     stopping on failure at any tier. This command is what CI and
     pre-push hooks invoke.

     Requirements:
     - Must run tiers in order: unit → contract → integration
     - A failure at any tier must block the next tier
     - Must return exit code 0 on success, non-zero on failure
     - Should support running a single tier (e.g., `./run-tests.sh unit`)

     Examples:
     - Bash: ./run-tests.sh
     - Python: pytest tests/unit && pytest tests/contract && pytest tests/integration
     - Makefile: make test
     - npm: npm test (with script that chains tiers)
-->

### Shared Test Helpers

<!-- Define common utilities that multiple specs' tests will use.
     These prevent duplication and ensure consistent test patterns.

     Typical helpers:
     - Setup/teardown: create and clean up temp directories, databases, etc.
     - Factories: generate test data conforming to shared definitions
     - Custom assertions: domain-specific pass/fail checks
     - Mock builders: reusable mocks for common dependencies
-->

### Installation and Dependencies

<!-- How are test dependencies installed?

     Examples:
     - Python: listed in pyproject.toml [test] extras or requirements-test.txt
     - Node: devDependencies in package.json
     - Bash: git submodules for bats-core
     - Go: no extra deps (go test is built-in)

     The installation method should be documented in CLAUDE.md and
     reproducible in CI without manual steps. -->

## Decisions

| ID | Decision | Alternatives Considered | Rationale | Date |
|----|----------|------------------------|-----------|------|
| T1 | <!-- Test framework choice --> | <!-- What else was considered --> | <!-- Why this one --> | <!-- Date --> |
| T2 | <!-- Test dependency installation method --> | <!-- Alternatives --> | <!-- Rationale --> | <!-- Date --> |

## Tests

### Unit Tests
<!-- The test infrastructure itself should be tested:
     - Entry point correctly runs tiers in order and stops on failure
     - Shared helpers produce valid fixtures
     - Custom assertions report correct pass/fail -->

### Contract Tests
N/A — no shared definition references. This is a foundational spec with no inbound contracts.

### Integration Tests
N/A — no cross-spec dependencies at Phase 0. Integration tests will be added when feature specs depend on the test harness.

## Environment Requirements

<!-- Declare runtime requirements for running tests.

     Examples:
     - "Python 3.10+ with venv"
     - "Node 18+ with npm"
     - "Bash 4+ and git"
     - "Docker for integration tests"
-->

## Implementation Notes

<!-- Guidance for the implementer:
     - Each test should be independent — setup creates fresh state, teardown cleans up
     - Tests must not mutate the project repo; all side effects in temp directories
     - Document the primary test command in CLAUDE.md's "Running Tests" section
     - Keep test dependencies minimal — don't add a test framework heavier than the project
-->
