---
name:
status: draft
owner: <group-name>
owns:
  -
requires:
  - name:
    version:
provides:
  - name:
    version:
---

<!-- Use this template when the spec shares data structures or contracts with
     other specs (Requires/Provides tables needed), has cross-spec dependencies,
     or has special environment requirements. For standalone specs, prefer
     spec-minimal.md instead. -->

# [Spec Name]

## Status
<!-- draft | ready | in-progress | implemented | revision-needed -->

## Target Phase
<!-- Which project phase(s) this spec is delivered in.
     A single phase: "Phase 0"
     Incremental delivery: "Phase 0 (validation only), Phase 2 (full implementation)"
     The register groups specs by phase for planning. -->

## Purpose
<!-- 1–3 sentences. What problem does this module solve and why does it exist
     as a distinct unit. -->

## Requires (Inbound Contracts)

<!-- What this spec needs from outside itself in order to be implemented.
     Every entry references either a shared definition or another spec's
     provides declaration.
     Keep in sync with the `requires:` frontmatter above (frontmatter is the
     machine-readable source of truth; this table is human-readable documentation). -->

| Dependency | Source | Definition |
|------------|--------|------------|

## Provides (Outbound Contracts)

<!-- What this spec makes available to the rest of the system.
     The Definition column references a shared definition for data shape
     contracts. For function/service interfaces that don't cross a shared
     definition boundary, the Definition column may be omitted or set to
     "inline" — describe the interface signature directly in the Export
     column instead.
     Keep in sync with the `provides:` frontmatter above (frontmatter is the
     machine-readable source of truth; this table is human-readable documentation). -->

| Export | Type | Definition |
|--------|------|------------|

## Behaviour

<!-- The detailed specification of what the code does. This is the core of
     the document. Write it with enough precision that an implementer
     (Claude Code) can produce correct code without asking questions.

     Structure this however suits the module: narrative prose,
     state machines, decision tables, endpoint-by-endpoint breakdowns.
     Avoid ambiguity. Where a design decision could go either way,
     pick one and state it. -->

## Decisions

<!-- Spec-scoped decisions: choices made during design that affect only this
     module. Record the decision, the alternatives considered, and why this
     option was chosen. This prevents relitigating settled questions.

     Decisions that affect 2+ specs belong in ARCHITECTURE.md's
     "Decisions and Rationale" section, not here. -->

| ID | Decision | Alternatives Considered | Rationale | Date |
|----|----------|------------------------|-----------|------|

## Tests

<!-- Define expected test coverage across applicable tiers.

     Unit tests (always required): Isolated tests for this spec's
     internal logic. Mock all external dependencies.

     Contract tests (required if this spec references shared
     definitions in Requires or Provides): Verify that exports conform
     to referenced definitions and imports are consumed correctly.
     If no shared definitions are referenced, write "N/A — no shared
     definition references" and explain why.

     Integration tests (required if this spec has cross-spec
     dependencies): Tests that exercise interaction with other specs.
     If this spec is standalone, write "N/A — no cross-spec
     dependencies" and explain why.

     Each test should be traceable to a specific behaviour above.
     Claude Code translates these into executable tests. -->

### Unit Tests
<!-- Always required. Isolated, mocked dependencies. -->

### Contract Tests
<!-- Required when shared definitions are referenced. Otherwise: "N/A — [reason]" -->

### Integration Tests
<!-- Required when cross-spec dependencies exist. Otherwise: "N/A — [reason]" -->

## Environment Requirements

<!-- Optional. Declare runtime environment dependencies that affect
     how the code is tested and deployed.

     Examples:
     - "Requires Spark 3.x — unit tests use local mode, integration
       tests require a Databricks cluster"
     - "Runs locally — no external dependencies"
     - "Notebook execution requires Databricks Runtime 14+"

     If omitted, the spec is assumed to be fully locally testable. -->

## Implementation Notes

<!-- Optional. Guidance on libraries, patterns, performance constraints,
     or anything that shapes *how* the code should be written without
     dictating it line-by-line. -->
