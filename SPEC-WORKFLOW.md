# Spec-Driven Development Workflow for Claude Code

## Principles

Every line of code in a project exists because a specification document called for it. No code is unowned. No specification is redundant with another. The system of documents forms a directed graph: architecture describes the whole, specifications describe the parts, shared definitions describe the contracts between parts, and a register maps it all to code.

Claude Code operates as an implementer, not an architect. It receives a specification and produces code that satisfies it. It does not invent structure, guess at interfaces, or make design decisions that belong at a higher level. When a specification is ambiguous or infeasible, Claude Code stops and says so rather than improvising.

### Collaborative Spec Authoring

Specs are a collaboration between the human (architecture owner) and Claude Code:

- **The human writes** Purpose and Behaviour — the design intent and detailed requirements. These are the hard parts that require domain knowledge and architectural judgment.
- **Claude Code fills** Requires/Provides tables, test stubs, decisions boilerplate, and other mechanical sections by deriving them from the architecture, shared definitions, and the Behaviour section.
- **The human reviews and approves** the completed spec before implementation begins.

This splits the work at the right seam: humans own *what* and *why*; Claude Code handles *traceability* and *structure*.

---

## Document Hierarchy

```
docs/
  ARCHITECTURE.md          # System-level design and cross-cutting decisions
  REGISTER.md              # Source-of-truth mapping (lookup table)
  definitions/             # Shared schemas, types, contracts
    billable-activity.md
    clinical-document.md
    claim.md
    ...
  specs/                   # Implementation specifications
    icd-validation.spec.md
    llm-extraction.spec.md
    rules-engine.spec.md
    project-infrastructure.spec.md
    test-infrastructure.spec.md
    ...
  reference/               # Domain knowledge, governance, and context
    consultation-types.md
    msp-fee-schedule.md
    ...
  plans/                   # Ephemeral implementation plans (not governed)
    ...
```

There are five kinds of document, plus ephemeral plans. Each has a distinct role. Nothing should blur the boundaries between the five governed types.

### Document Roles

| Document | Answers | Owned By |
|---|---|---|
| Architecture | What are the components and how do they connect? | Architecture owner |
| Shared Definition | What is this data structure / contract? | Architecture (not any single spec) |
| Specification | What does this module do, need, and provide? | Spec owner |
| Register | Where does everything live and how does it connect? | Manually maintained; audited each implementation cycle |
| Reference | What domain knowledge informs the design? | Architecture owner (or a spec, if tightly scoped) |

### Reference Documents

Reference documents hold domain knowledge, governance artifacts, business context, and other material that informs specs but is not itself a specification, definition, or architectural document. Examples:

- MSP fee code catalogs
- Project charters and business cases
- Regulatory reference material
- Data quality notes and domain rules

Reference documents have no required template. They are acknowledged by the workflow but outside the ownership and versioning model. Specs may cite them in their Implementation Notes or Behaviour sections. The architecture document may reference them for context.

### Implementation Plans

Plans (`docs/plans/`) are ephemeral operational documents — step-by-step task breakdowns for implementing a spec. They are useful during implementation but are not governed artifacts. Each plan references a spec but is not owned by the workflow. Once a spec reaches `implemented` status, its plan is historical context only.

---

## 1. Shared Definitions

Shared definitions are the canonical source of truth for any data structure, interface signature, event schema, error format, or type that more than one specification references. They are also the correct home for any such structure that *could* be referenced by more than one specification, even if currently only one does — this prevents inline definitions from silently diverging later.

A shared definition describes *what* something is, not *how* it is implemented. It is owned by the architecture, not by any single spec.

### Versioning

Shared definitions use **simple integer versions**: v0, v1, v2, v3.

**Draft definitions use v0.** While a definition has status `draft`, its version stays at v0. Changes to a v0 definition do not require consuming specs to re-pin — the definition is still being shaped. When the definition moves to `stable`, it becomes v1 and normal versioning rules apply from that point forward. This prevents constant version churn during initial design.

**Stable definitions use v1+.** Once stable:

- Every version increment is treated as a **breaking change**.
- When a definition is bumped from vN to vN+1, **all consuming specs must review and re-pin**.
- The version is recorded in the definition's `## Version` header, in every spec's requires/provides table that references it, and in `contracts.yaml`.
- There is no concept of backward-compatible or minor changes. If the definition changes, the version increments. Period.

This is deliberately conservative. The cost of reviewing a non-breaking bump is low. The cost of missing a breaking change because it was labelled "minor" is high.

### Version Pin Mechanism

Version pins are tracked in three places, which must be kept in sync:

1. **The definition's `## Version` header** — the canonical current version.
2. **Each spec's Requires/Provides tables** — the version each spec is pinned to.
3. **`contracts.yaml`** — a central file mapping spec → definition → pinned version, used by contract tests to detect staleness programmatically.

The `contracts.yaml` file lives at the project root and has this structure:

```yaml
# contracts.yaml — version pins for contract test enforcement
# This file must match the Requires/Provides tables in each spec.
# Contract tests read this file to verify version alignment.

specs:
  icd-validation.spec:
    requires:
      definitions/query-interface.md: v1
  llm-extraction.spec:
    requires:
      definitions/specialty-config.md: v1
      definitions/extracted-data.md: v1
    provides:
      definitions/extracted-data.md: v1
```

Contract tests import version pins from this file and compare against the definition files' current versions. A mismatch fails the test.

### Definition Template

```markdown
# [Definition Name]

## Status
<!-- draft | stable | deprecated -->

## Version
<!-- v0 while draft. v1+ once stable.
     Increment on ANY change to a stable definition. Every bump is breaking.
     All consuming specs must review and re-pin. -->

## Description
<!-- What this definition represents and why it exists as a shared contract. -->

## Schema
<!-- The canonical structure. Use the notation natural to the project:
     Python dataclasses, JSON Schema, SQL DDL, or plain structured
     prose — but pick one notation per project and use it everywhere. -->

## Constraints
<!-- Validation rules, invariants, allowed ranges, nullability,
     anything a consumer or provider must respect. -->

## Changelog
<!-- Date, version, what changed, which specs are affected. -->

| Date | Version | Change | Affected Specs |
|------|---------|--------|----------------|
```

### Governing Rules

- No specification may define a data structure inline if that structure crosses a module boundary. It must reference a shared definition.
- When two specs need to agree on a shape, that shape lives here — not in either spec.
- Changing a shared definition is an architectural act. The architecture owner approves the change. It triggers review of every spec that provides or requires it (the register makes this lookup trivial).

---

## 2. Specification Documents

A specification is the sole authority over a bounded piece of implementation. It declares what the code must do, what it provides to the rest of the system, what it requires from the rest of the system, and how correctness is verified.

### Spec Sizing

A spec should have a **single reason to change**. If two behaviours in a spec can evolve independently without affecting each other, they should be separate specs. Conversely, if two pieces of code always change together and share internal state, they belong in the same spec.

Signs a spec is too large:
- Its Behaviour section has multiple unrelated subsystems (e.g., "physician resolution" and "facility mapping" have nothing in common).
- Different parts of it could be implemented and tested independently.
- It owns files in multiple unrelated directories.

Signs a spec is too small:
- It cannot be tested without mocking its own internals.
- Its provides are only consumed by one other spec and could be inlined.
- It has no independent reason to exist — it was split for organizational neatness, not because the pieces genuinely evolve independently.

### Status State Machine

Specs progress through these statuses:

```
draft ──→ ready ──→ in-progress ──→ implemented
  ↑                      │                │
  │                      ↓                ↓
  └──────────── revision-needed ←─────────┘
```

| Transition | Trigger |
|---|---|
| `draft` → `ready` | Architecture owner confirms: Behaviour is complete, all Requires are satisfiable, shared definitions exist (at least at v0). |
| `ready` → `in-progress` | Implementation work begins. |
| `in-progress` → `implemented` | All code written, all applicable tests pass, register updated. |
| `in-progress` → `revision-needed` | Ambiguity, infeasibility, or incorrectness discovered during implementation (see §7 Revision Protocol). |
| `implemented` → `revision-needed` | A shared definition changes, a dependent spec changes, or a defect is found. |
| `revision-needed` → `draft` | Spec is being reworked. Returns to `draft` for significant rewrites, or directly to `ready` for minor fixes. |
| `revision-needed` → `ready` | Fix applied, spec is ready for re-implementation. |

### Spec Templates

There are two spec templates, chosen based on the spec's complexity:

| Template | File | When to use |
|---|---|---|
| **Minimal** | `docs/templates/spec-minimal.md` | Default. Standalone specs with no shared definitions or cross-spec dependencies. |
| **Full** | `docs/templates/spec-full.md` | Specs that share data structures with other specs, have cross-spec dependencies, or require special environment declarations. |

**Use minimal by default.** Complex specs that genuinely need Requires/Provides tables, environment declarations, and multi-tier tests can use the full template. But requiring every spec to fill those sections out (even with N/A) creates ceremony without value.

The full template's `requires:` and `provides:` frontmatter fields are the **machine-readable source of truth** for contract tooling. The Requires/Provides tables in the body are the human-readable documentation — they should be kept in sync.

#### Minimal Template

```markdown
---
name:
status: draft
owner: <@owner>
owns:
  -
---

#

## Purpose

<!-- 1–3 sentences: what this module does and why it exists. -->

## Behaviour

<!-- The detailed specification of what the code does. Write it with enough
     precision that an implementer (Claude Code) can produce correct code
     without asking questions. -->

## Tests

### Unit Tests

<!-- Isolated tests for this spec's internal logic. Mock all external
     dependencies. One test per distinct behaviour. -->
```

#### Full Template

```markdown
---
name:
status: draft
owner: <@owner>
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

## Owner
<!-- Who is responsible for this spec's correctness and currency. -->

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

| Dependency         | Source                          | Definition                          |
|--------------------|---------------------------------|-------------------------------------|
| Authenticated user | auth-service.spec provides      | definitions/auth-token.md@v1        |
| User record        | shared                          | definitions/user-schema.md@v2       |

## Provides (Outbound Contracts)

<!-- What this spec makes available to the rest of the system.
     The Definition column references a shared definition for data shape
     contracts. For function/service interfaces that don't cross a shared
     definition boundary, the Definition column may be omitted or set to
     "inline" — describe the interface signature directly in the Export
     column instead.
     Keep in sync with the `provides:` frontmatter above (frontmatter is the
     machine-readable source of truth; this table is human-readable documentation). -->

| Export                  | Type              | Definition                          |
|-------------------------|-------------------|-------------------------------------|
| GET /api/users/:id      | REST endpoint     | definitions/user-schema.md@v2       |
| validate_icd9(code)→bool| Function          | (inline)                            |

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

     **Unit tests** (always required): Isolated tests for this spec's
     internal logic. Mock all external dependencies.

     **Contract tests** (required if this spec references shared
     definitions in Requires or Provides): Verify that exports conform
     to referenced definitions and imports are consumed correctly.
     If no shared definitions are referenced, write "N/A — no shared
     definition references" and explain why.

     **Integration tests** (required if this spec has cross-spec
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
```

### Context File Derivation

Specs do **not** contain a manually maintained context file list. Instead, Claude Code derives the context automatically before implementation:

1. Read `docs/ARCHITECTURE.md` (always — for orientation).
2. Read the spec being implemented.
3. From the spec's **Requires** table, resolve each dependency:
   - If the source is a shared definition: read that definition file.
   - If the source is another spec's provides: read that spec file.
4. Consult `docs/REGISTER.md` to find the **owned files** of each required spec — read those implementation files if they exist.
5. Read any files listed in the spec's **Implementation Notes** section.

This derivation is deterministic, always up-to-date, and cannot go stale independently of the requires table.

### Governing Rules

- Every source file in the project is owned by exactly one spec. No exceptions. Infrastructure and cross-cutting files are owned by `project-infrastructure.spec` or `test-infrastructure.spec` (see §5).
- A spec may own many files. A file may not be owned by many specs.
- Shared/utility code that serves multiple modules gets its own spec. The first spec that needs a shared utility does not own it — a dedicated spec is created and the code is moved there.
- If Claude Code encounters an ambiguity during implementation, it must surface it as an unresolved question rather than choosing an interpretation. The spec is then revised. (See §7 for draft-mode exceptions.)
- Tests defined in the spec are authoritative. Claude Code may add supplementary tests, but may not skip or weaken any spec-defined test.

---

## 3. Architecture Document

The architecture document describes the system as a whole. It does not describe implementation details — those belong in specs. It answers: what are the major components, how do they relate, what data flows between them, and what shared definitions govern the boundaries.

The architecture document also names the **architecture owner** — the person or role with final authority over cross-cutting decisions, shared definition changes, and conflict resolution between specs.

**Size constraint:** The architecture document is a map, not a manual. It should stay under approximately **5,000 words**. Detailed component descriptions, data flow narratives, and decision rationale belong in specs and their referenced definitions — not in the architecture document. If the architecture document is growing beyond this limit, content should be pushed down into specs.

### Architecture Template

```markdown
# [Project Name] — Architecture

## Architecture Owner
<!-- The person or role with final authority over shared definitions,
     cross-spec conflicts, and architectural decisions. -->

## Overview
<!-- What does this system do, at the highest level. Who/what are
     its users and external dependencies. -->

## Components
<!-- Name each major component/module. For each: a 1–2 sentence
     description of its responsibility, and which spec owns it. -->

## Phase Map
<!-- Which specs are delivered in which phase. Derived from
     each spec's Target Phase field. -->

| Phase | Specs | Goal |
|-------|-------|------|

## Data Model
<!-- The key entities and their relationships. Reference shared
     definitions for schemas. An ERD or equivalent diagram is
     appropriate here. -->

## Data Flows
<!-- How data moves through the system. Identify the major
     workflows and describe them as sequences of component interactions.
     Reference the provides/requires contracts. -->

## Integration Points
<!-- External APIs, databases, third-party services. What shared
     definitions govern these boundaries. -->

## Cross-Cutting Concerns
<!-- Authentication, logging, error handling, configuration —
     anything that spans multiple specs. Identify which spec
     owns each concern and which shared definitions apply. -->

## Dependency Graph
<!-- Which specs depend on which other specs, derived from the
     provides/requires declarations. This determines implementation
     order within each phase. Can be a list, a table, or a
     Mermaid diagram. -->

## Decisions and Rationale
<!-- Cross-cutting decisions that affect 2+ specs.
     Spec-scoped decisions live in each spec's Decisions section.

     Record: the decision, alternatives considered, rationale,
     and which specs are affected. -->

| ID | Decision | Alternatives | Rationale | Affected Specs | Date |
|----|----------|-------------|-----------|----------------|------|
```

### Conflict Resolution

The architecture owner is the final authority when:

- Two specs need to modify the same shared definition in incompatible ways.
- A shared definition change breaks multiple specs and prioritization is needed.
- Two specs claim overlapping file ownership.
- A design decision could reasonably go either way and the affected spec owners disagree.

The process is: affected spec owners surface the conflict with their preferred options. The architecture owner decides. The decision is recorded in the architecture document's "Decisions and Rationale" table with the rationale and affected specs.

---

## 4. The Register

The register is the single source of truth for what exists, where it lives, and how it connects. It is a lookup table, not a narrative document. It is **manually maintained** — after every spec implementation or definition change, Claude Code updates the register as a required step. If the register is stale, the system is broken.

### Register Audit

After every implementation cycle (implementing a spec, changing a definition, or modifying architecture), Claude Code performs a register audit:

1. Verify that every file listed in the register's "Owns" column exists on disk.
2. Verify that every source file on disk is listed in exactly one spec's "Owns" column.
3. Verify that the register's version pins match the current definition versions.
4. Verify that the register's dependency links match the specs' Requires tables.
5. Report any discrepancies for resolution before proceeding.

### Register Structure

```markdown
# Project Register

## Definitions Index

| Definition                      | Version | Status  | Primary Implementor       | Required By                         |
|---------------------------------|---------|---------|---------------------------|-------------------------------------|
| definitions/user-schema.md      | v2      | stable  | user-api.spec             | dashboard-ui.spec, auth-service.spec|
| definitions/auth-token.md       | v1      | stable  | auth-service.spec         | user-api.spec, dashboard-ui.spec    |
| definitions/api-error-format.md | v1      | stable  | external (third-party API)| user-api.spec, auth-service.spec    |

## Spec Index

| Spec                             | Phase | Status       | Owns (files/directories)       | Depends On                  |
|----------------------------------|-------|--------------|--------------------------------|-----------------------------|
| project-infrastructure.spec.md   | 0     | implemented  | pyproject.toml, setup.cfg, ... | (none)                      |
| test-infrastructure.spec.md      | 0     | implemented  | tests/conftest.py, ...         | (none)                      |
| auth-service.spec.md             | 1     | implemented  | src/auth/**                    | (none)                      |
| user-api.spec.md                 | 1     | in-progress  | src/api/users/**               | auth-service.spec           |
| dashboard-ui.spec.md             | 2     | ready        | src/ui/dashboard/**            | user-api.spec               |

## Phase Summary

| Phase | Specs (count) | Status |
|-------|--------------|--------|
| 0     | 2            | implemented |
| 1     | 2            | in-progress |
| 2     | 1            | ready |

## Unowned Code
<!-- This section should always be empty. If it is not, something
     needs to be assigned to a spec or deleted. -->

## Dependency Resolution Order
<!-- Topological sort of the spec dependency graph, grouped by phase.
     This is the order in which specs should be implemented. -->

### Phase 0
1. project-infrastructure.spec
2. test-infrastructure.spec

### Phase 1
3. auth-service.spec
4. user-api.spec

### Phase 2
5. dashboard-ui.spec
```

The **Primary Implementor** column in the Definitions Index identifies the spec whose implementation is the canonical expression of this definition. For definitions that represent external interfaces (e.g., third-party APIs, database schemas not owned by the project), use `external (description)`. This column does not imply ownership — all definitions are owned by the architecture, not by any single spec.

---

## 5. Reserved Specs

Two specs are always present in every project. They are created during project setup and own the cross-cutting infrastructure that no feature spec should claim.

### project-infrastructure.spec

Owns all project-level files that are not part of any feature module:

- Build configuration (`pyproject.toml`, `setup.cfg`, `Makefile`, etc.)
- CI/CD configuration (`.github/workflows/`, etc.)
- Root-level package files (`<package>/__init__.py`, etc.)
- Documentation infrastructure (`CLAUDE.md`, `docs/` structure)
- Development configuration (`.gitignore`, `.pre-commit-config.yaml`, etc.)
- Dependency management (`requirements.txt`, lock files)
- Version pin tracking (`contracts.yaml`)

This spec's **Provides** section declares the project skeleton: directory structure, entry points, and configuration interfaces that other specs depend on.

### test-infrastructure.spec

Owns all cross-cutting test infrastructure:

- Test framework configuration (`pytest.ini`, `conftest.py` at root and shared levels)
- Shared fixtures and factories used by multiple specs
- Golden datasets and reference test data (`ref/`, test data directories)
- Integration test harnesses that execute cross-spec scenarios
- Test utilities (custom assertions, mock builders, etc.)

Integration tests are **defined** by the specs that participate in them (in each spec's "Integration Tests" subsection) but **executed** by the test infrastructure. This means:
- Each spec author writes the integration test *scenarios* they care about.
- `test-infrastructure.spec` owns the *harness* and *shared fixtures* that make those scenarios runnable.
- The test-infrastructure spec does not invent integration tests — it implements the ones specs declare.

---

## 6. Testing Strategy

Every spec must define tests across applicable tiers. Unit tests are always required. Contract and integration tests are required when the spec has the relevant contracts — otherwise, the spec must explicitly declare them N/A with a reason.

### Tier 1: Unit Tests

- **Scope**: Single spec in isolation. All external dependencies mocked.
- **Owned by**: The spec being tested.
- **Location**: `tests/unit/<module>/` mirroring the source structure.
- **Runs**: On every change to the spec's owned files.
- **Purpose**: Verify internal logic and edge cases.
- **Required**: Always.

### Tier 2: Contract Tests

- **Scope**: Verify that a spec's implementation matches its declared contracts.
- **Owned by**: The spec being tested (defined in spec) + test-infrastructure (harness).
- **Location**: `tests/contract/<module>/`.
- **Checks**:
  - Each **provides** export conforms to its referenced shared definition (correct schema, constraints satisfied).
  - Each **requires** import is consumed correctly per the definition's constraints.
  - Version pins in `contracts.yaml` match the current definition versions.
- **Purpose**: Catch definition drift. If a shared definition bumps from v1 to v2, contract tests for all consuming specs should fail until they update.
- **Required**: When the spec references shared definitions in Requires or Provides. If no shared definitions are referenced (e.g., a standalone utility), the spec declares "N/A — no shared definition references."

Contract tests are partially **derivable from the spec's tables**: the requires/provides declarations specify exactly what to check. Claude Code should generate contract test skeletons from these tables.

### Tier 3: Integration Tests

- **Scope**: Two or more specs interacting through their provides/requires contracts.
- **Owned by**: test-infrastructure.spec (harness) + participating specs (scenarios).
- **Location**: `tests/integration/`.
- **Runs**: After all participating specs pass their unit and contract tests.
- **Purpose**: Verify that the specs work together as the architecture describes.
- **Required**: When the spec has cross-spec dependencies. If the spec is standalone with no cross-spec interactions, it declares "N/A — no cross-spec dependencies."

### Test Execution Order

Tests run in tier order: unit → contract → integration. A failure at any tier blocks the next tier. This is enforced by CI, not by convention.

### Staleness Detection via Tests

Contract tests serve double duty as staleness detectors:
- When a shared definition version is bumped, contract tests for specs still pinned to the old version will fail.
- This failure is the *mechanism* by which version mismatches are caught — not manual register inspection.

---

## 7. Claude Code Workflow

### Starting a New Project

1. **Write the architecture document first.** Define components, data model, data flows, cross-cutting concerns, and name the architecture owner. Do not write any specs yet.
2. **Create the reserved specs.** Write `project-infrastructure.spec.md` and `test-infrastructure.spec.md`. These are always Phase 0.
3. **Extract shared definitions.** Any data structure, interface, or contract that appears in the architecture's data flows or component boundaries becomes a shared definition document. Set all to v0 (draft).
4. **Write feature specs.** One per component or module identified in the architecture. Each spec declares its provides and requires (referencing shared definitions by path and version), its target phase, and its tests across applicable tiers.
5. **Build the register.** Populate the definitions index and spec index. Group by phase. Derive the dependency resolution order within each phase.
6. **Create `contracts.yaml`.** Populate version pins from all specs' Requires/Provides tables.
7. **Audit the register.** Before implementation begins, run all five steps of the register audit (§4). This catches cross-referencing errors before they compound during implementation.
8. **Implement in phase + dependency order.** Within each phase, start with specs that have no unmet dependencies. For each spec, derive the context (§2), implement the code, write the tests, and report any ambiguities.

**Creation order is strict.** Do not implement code until the full dependency chain of documents exists: architecture → shared definitions → specs → register → contracts.yaml. This applies during both initial setup and migration from legacy documents.

### Migrating an Existing Project

When applying this workflow to an existing project with legacy documents, follow the migration path rather than the greenfield "Starting a New Project" sequence. The same strict creation order applies — migration does not skip steps.

The migration proceeds through five phases:

1. **Inventory.** Catalog all existing documents and source files.
2. **Classify.** For each legacy document, assign a disposition: archive, keep as reference, decompose into governed artifacts, or split a monolith document into chunks and classify each chunk. For chunks marked "decompose," annotate the target artifact type (architecture, definition, or spec).
3. **Extract.** Follow the strict creation order (§1–§5): architecture → reserved specs → shared definitions → feature specs. Use draft status liberally — don't aim for perfection on the first pass.
4. **Build traceability.** Create the register and `contracts.yaml`. Assign file ownership. Expect iteration between this phase and the next.
5. **Validate.** Run the full register audit (§4) and health check (see Health Check Procedure below). Resolve all discrepancies. Archive original legacy documents.

This is typically a one-time procedure per project. For the detailed walkthrough including decision guidance, judgment-call heuristics, and common pitfalls, see `docs/reference/migration-guide.md`.

### Implementing a Spec

When Claude Code receives a task to implement a spec:

1. **Derive context.** Follow the context derivation procedure (§2): read architecture, read the spec, resolve all requires to their definition and implementation files via the register.
2. **Check staleness.** Verify that all requires reference current definition versions (compare spec pins and `contracts.yaml` against definition files). If any are stale, stop and report.
3. **Confirm requires are satisfied.** All required specs must be either implemented or stubbed with a known interface.
4. **Implement the code.** Every source file created must be listed as owned by this spec in the register.
5. **Write all tests.** Unit, contract (if applicable), and integration (if applicable) tests as defined in the spec. Run them in tier order.
6. **Record decisions.** Any design choices made during implementation that aren't already in the spec are recorded in the spec's Decisions table.
7. **If any spec-defined behaviour is ambiguous or infeasible, follow the appropriate protocol** (see Draft Mode and Revision Protocol below).
8. **Update the register.** Set spec status, list owned files, confirm dependency links, update phase summary.
9. **Audit the register.** Run all five steps of the register audit checklist (§4) to verify consistency. For first-time implementation after project setup or migration, this audit is especially critical — it is the first point where cross-referencing errors between specs, definitions, and contracts.yaml will surface.

### Draft Mode

When all involved documents (the spec being implemented and its required definitions) have status `draft`:

- Claude Code **notes ambiguities** in the spec's Decisions table and **continues with its best interpretation**, rather than stopping.
- Hard stops are reserved for **contradictions** (the spec says two incompatible things) and **infeasibility** (the approach cannot work as described).
- Minor TBDs, stylistic choices, and questions about edge cases are logged and implementation proceeds.

This prevents the workflow from grinding to a halt during early development when everything is being shaped simultaneously. Once documents move to `ready` or `stable`, the strict "stop and report" rule applies.

### Revision Protocol

When Claude Code discovers during implementation that a spec's approach is incorrect (not ambiguous, but wrong — an API doesn't exist as described, a performance constraint makes the design infeasible, etc.):

1. **Stop implementation** of the affected behaviour.
2. **Document the finding**: what was attempted, what failed, and why the spec's approach won't work.
3. **Propose alternatives**: suggest 1-3 alternative approaches with trade-offs.
4. **Set the spec's status to `revision-needed`**.
5. **Continue implementing unaffected parts** of the spec if they are independent.
6. **The architecture owner reviews** the proposal, selects an approach, and updates the spec. The spec then returns to `ready` or `draft` for re-implementation.

This is distinct from ambiguity (where the spec doesn't say enough) — this is about the spec being wrong. The revision protocol creates a structured path for implementation feedback to flow back into design.

### Handling Change

**When a shared definition changes:**
1. The architecture owner approves the change.
2. Increment the definition's version (v1 → v2).
3. Update the definition's changelog with date, change description, and affected specs.
4. Consult the register's definitions index to find all specs that provide or require it.
5. Update `contracts.yaml` with the new version.
6. Run contract tests for all affected specs — they should fail on the old version pin.
7. Update each affected spec's requires/provides version pins.
8. Re-implement or update code for affected specs. Re-run all applicable test tiers.
9. Update the register.

**When a spec changes:**
1. Update the spec document.
2. Consult the register to find owned files — those need updating.
3. Consult the register to find specs that depend on this one (via its provides) — those may need review.
4. Re-run all applicable test tiers for the changed spec and all dependent specs.
5. Update the register.

**When architecture changes:**
1. The architecture owner makes the change.
2. Determine which specs and definitions are affected.
3. Update definitions first (bump versions), then specs (update pins), then `contracts.yaml`, then code — always top-down.
4. Record the change in the architecture's Decisions and Rationale table.

### Detecting Staleness

Code is stale when any of the following are true:
- The spec it belongs to has status `revision-needed`.
- The spec's requires reference a definition version older than the current version.
- `contracts.yaml` pins don't match the spec's Requires tables.
- The register's owned-files list does not match what actually exists on disk.
- Contract tests fail.

Claude Code checks for staleness as the **first step** before any implementation task. The check is:
1. Read the register.
2. For each spec in scope, compare its requires version pins against the current definition versions in the definitions index.
3. Compare `contracts.yaml` against both spec pins and definition versions.
4. If any mismatch: stop and report which specs are stale and which definitions triggered it.

### Health Check Procedure

When consistency is uncertain (e.g., returning to a project after a break, or after multiple changes across specs), Claude Code can run a full health check:

1. **Register vs. disk**: Verify every file in the register exists, and every source file on disk appears in exactly one spec's ownership.
2. **Imports vs. Requires**: For each spec's owned files, audit Python imports against the spec's declared Requires. Flag any import from another spec's owned module that isn't declared as a dependency.
3. **contracts.yaml vs. specs**: Verify that every pin in `contracts.yaml` matches the corresponding spec's Requires/Provides table.
4. **contracts.yaml vs. definitions**: Verify that every pin in `contracts.yaml` references a version that exists in the corresponding definition file.
5. **Spec status consistency**: Verify that no spec with status `implemented` has failing tests, and no spec with status `draft` has owned implementation files.
6. **Produce a drift report**: List all discrepancies with specific files, specs, and suggested fixes.

This procedure is run on-demand, not automatically. It produces a report — it does not fix anything without architecture owner approval.

---

## 8. Spec-First Gate

All code changes flow through specs. Users do not request code directly — they request spec changes, and code is derived from specs. This is the central enforcement rule of the workflow.

### The Gate Rule

Claude Code **must not** modify, create, or delete source files unless it is implementing a spec with status `in-progress`. If a user requests a code change directly (e.g., "add retry logic to the HTTP client"), Claude Code must:

1. Identify which spec owns the affected code (via the register).
2. Ask the user to update the spec's Behaviour section to describe the desired change — or offer to draft the spec change for the user's review.
3. Wait for the user to approve the spec change.
4. Only then proceed with implementation.

This applies to all owned source files. It does not apply to governed documents themselves (specs, definitions, architecture, register) — those are edited as part of the workflow, not gated by it.

### Permitted Without a Spec Change

Not every action requires a spec update. The following are permitted without modifying a spec's Behaviour section:

**Implementation-detail refactoring.** Restructuring code that preserves all spec-defined behaviour. The spec describes *what* and *why*, not *how*. Internal reorganization (renaming private helpers, simplifying control flow, improving performance without changing interfaces) is allowed as long as all tests continue to pass. Record the refactoring in the spec's Decisions table with rationale.

**Patch fixes.** Bug fixes where the code does not match what the spec already says. If the spec says "validate ICD-9 codes against the master list" and the code has an off-by-one error in the validation loop, the spec is already correct — the code is wrong. Fix the code, add a Patches entry (see below), and ensure tests cover the bug. If the fix reveals that the spec's *behaviour description* was wrong or incomplete, that requires a spec change.

**Test additions.** The spec's test section is authoritative, but Claude Code may add supplementary tests that strengthen coverage without changing spec-defined behaviour. These are additions, not modifications to spec-defined tests.

### Patches Section

Add this optional section to the spec template, after Implementation Notes:

```markdown
## Patches

<!-- Bug fixes where the code was corrected to match existing spec behaviour.
     These do not require a spec change because the spec was already correct —
     the implementation was wrong.

     If a fix reveals that the spec's behaviour description was wrong or
     incomplete, use the Revision Protocol instead. -->

| Date | Description | Files Changed |
|------|-------------|---------------|
```

### Spikes

When exploratory work is needed before a spec can be written — evaluating a library, testing an API's actual behaviour, prototyping an approach — use a spike.

A spike is **throwaway code** that exists to answer a question. It is not governed by the spec workflow:

- Spike code lives in a dedicated directory (e.g., `spikes/` or a feature branch) and is never merged into spec-owned code.
- A spike has a clear question it is answering and a timebox.
- The output of a spike is *knowledge* (captured in a spec or architecture decision), not code.
- Once the question is answered, the spike code is deleted. Any useful patterns are re-implemented properly through a spec.

Spikes prevent the spec-first gate from blocking genuine exploration. They also prevent exploration from silently becoming production code.

### Code-First Workflow

Not all work starts with a spec. When you need to explore, prototype, or iterate before formalizing, use the code-first path:

1. Create a feature branch
2. Write code (explore, prototype, iterate)
3. Run `/consolidate` to generate specs from your code
4. Review and refine the generated specs
5. Run `/health-check` to verify governance is clean
6. Run `/pr` to ship

This is a first-class workflow, not a remediation step. The spec-first gate (above) ensures governed code has specs — the code-first path is how you get there when the code comes first.

### Why This Works With AI Implementation

In traditional development, spec-first workflows create friction because the same person writes both the spec and the code — the spec feels like paperwork before the "real work." With AI implementation, the equation inverts:

- The human's *only* job is expressing intent precisely (the spec).
- The AI's job is translating that intent into correct code.
- The spec is not overhead — it is the primary interface between human domain knowledge and AI code generation.

This means spec quality directly determines code quality. A vague spec produces vague code. A precise spec produces precise code. The gate rule ensures that the human's effort goes where it has the highest leverage: the spec.

---

## 9. Git Workflow

This section describes how work is initiated and how git is used. It is guidance, not enforcement — this is a solo-dev + AI workflow, not a team process.

### Work Initiation: Issues First

All work starts as a GitHub issue — new specs, definition changes, bug fixes, workflow improvements. Issues are the canonical record of *why* work happened; specs define *what*; code defines *how*.

When generating specs or starting implementation, reference the originating issue (e.g., "Implements #12" in a spec's Purpose section or commit messages).

### Branching

One branch per issue. Branch from `main`, merge back to `main`.

**Naming convention:** `<type>/issue-<number>-<short-description>`

Examples:
- `feat/issue-12-add-user-auth`
- `fix/issue-7-health-check-bash-compat`
- `docs/issue-15-git-workflow-guidance`
- `infra/issue-20-ci-pipeline`

Types are kept minimal: `feat`, `fix`, `docs`, `infra`. They are not enforced by tooling.

### Pull Requests

- PRs link back to their issue (`Closes #N` in the PR description).
- PR description should note which specs or definitions were created or changed.
- Merge to `main` = work is done; spec status should reflect this (e.g., `implemented`).

### How Spec Lifecycle Maps to Git

| Activity | Issue | Branch |
|---|---|---|
| Creating a new spec | Issue describing the need | Branch for drafting the spec |
| Implementing a spec | Same issue, or a new one for implementation | Branch for implementation |
| `revision-needed` | New issue describing what's wrong | Branch for the fix |
| Definition version bump | Issue tracking the change and affected specs | Branch for the update |

### What This Does NOT Prescribe

- No required issue templates (though they could be added later)
- No CI enforcement of branch naming or PR structure
- No required approvals (solo dev)
- No release branches or tags (add when needed)

---

## 10. Anti-Patterns

- **Inline schemas.** A spec defines a data structure that another spec also needs. Now there are two sources of truth. Fix: extract to a shared definition.
- **Orphan code.** Files exist that no spec claims. They accumulate implicit behaviour that no one is accountable for. Fix: assign to a spec or delete.
- **Spec-to-spec coupling.** Spec A directly references Spec B's internals rather than going through a shared definition. Fix: extract the interface to a definition; both specs reference it.
- **Ghost dependencies.** A spec uses something from another module without declaring it in requires. The code works by accident. Fix: audit imports against declared requires.
- **Architecture drift.** The architecture document describes a system that no longer matches the specs. Fix: architecture is updated whenever specs are added, removed, or fundamentally changed.
- **Junk-drawer specs.** A spec like "shared-utils" accumulates unrelated code from many features. Fix: split into purpose-specific specs. A shared utility for date handling and a shared utility for error formatting are two specs, not one. Apply the sizing heuristic: if two behaviours can evolve independently, they should be separate specs.
- **Stale decisions.** A decision was made, recorded, and later invalidated by a subsequent change — but the record was never updated. Fix: when a decision is revisited, update or supersede the original entry with a reference to the new one.
- **Phase leakage.** Implementation work bleeds into a phase it wasn't planned for, pulling in unready dependencies. Fix: specs declare their target phase; the register enforces phase boundaries; dependency order is computed within phases.
- **Premature strictness.** Applying stable-definition rules (version bumps, mandatory re-pinning) to draft documents that are still being shaped. Fix: use v0 for draft definitions; apply strict versioning only after the definition reaches `stable`.
