# RuleFlow Engine — Architecture

## Architecture Owner

Project maintainer

## Overview

RuleFlow Engine is the core logic layer of the RuleFlow framework — a system for converting business rules and clinical protocols into interactive decision tree wizards. The engine provides three independent capabilities: schema traversal (step-by-step wizard state machine), schema analysis (validation and gap detection), and schema visualization (Mermaid flowchart generation). All three operate on the same data shape — the `RuleFlowSchema` type — defined in a shared definition. The engine has zero framework dependencies and runs in both browser and Node.js environments.

## Components

- **Traverser** (`traverser.spec`) — Pure state machine for step-by-step schema traversal. Accepts a schema and user selections, produces immutable state transitions, and tracks history for back-navigation. Provides the primary implementor for `types.ts`.
- **Analyzer** (`analyzer.spec`) — Schema validator that produces structured analysis reports. Performs three-tier checking: structural errors (invalid graph structure), logic warnings (coverage gaps, conflicts), and style info (UX improvement suggestions).
- **Mermaid Generator** (`mermaid-generator.spec`) — Converts a schema into a Mermaid `flowchart TD` string for documentation and visual review. BFS traversal with depth limiting and category-based result coloring.
- **Schema Types** — Shared type definitions defined in `definitions/ruleflow-schema.md@v1` (owned by the architecture). `types.ts` is the canonical TypeScript expression; `traverser.spec` is the primary implementor per the register.

## Phase Map

| Phase | Specs | Goal |
|-------|-------|------|
| 0 | project-infrastructure, test-infrastructure | Build system, test harness, CI/CD |
| 1 | traverser, analyzer, mermaid-generator | Core engine functionality |

## Data Model

The system operates on a single core data structure: `RuleFlowSchema` (defined in `definitions/ruleflow-schema.md@v1`). A schema contains:

- **Variables** — the decision state space (enum and boolean types)
- **Nodes** — decision points, each with a question and an array of options that set variables and point to the next node or result
- **Results** — terminal outcomes with title, detail, category, severity, and tags
- **Metadata** — provenance information (institution, source, authors, disclaimer)
- **Display** — optional theming (colors, fonts, category color mappings, branding)

## Data Flows

All three engine modules follow a single-pass, input-to-output pattern:

- **Traverser:** `RuleFlowSchema` + user selections → state transitions → `TraverserState` (including terminal result)
- **Analyzer:** `RuleFlowSchema` → structural checks → logic checks → style checks → `AnalysisReport`
- **Mermaid Generator:** `RuleFlowSchema` → BFS traversal → Mermaid flowchart string

No module modifies the input schema. All are pure functions.

## Integration Points

None. The engine is a pure library with no external API calls, database connections, or third-party service dependencies. It accepts JSON schemas as input and produces typed outputs.

## Cross-Cutting Concerns

- **Goto resolution** — Parsing the `result:` prefix to distinguish node targets from result terminals, and resolving conditional gotos against variable state. This logic is reimplemented independently by both the traverser and the analyzer (see Decision ARCH-2). The mermaid generator also parses goto targets but does not resolve conditionals against state.
- **Schema validation** — The shared definition enforces type-level constraints. Runtime validation (structural integrity, coverage completeness) is the analyzer's exclusive responsibility.

## Dependency Graph

```
definitions/ruleflow-schema.md@v1
    ├── traverser.spec (primary implementor + consumer)
    ├── analyzer.spec (consumer)
    └── mermaid-generator.spec (consumer)
```

All three engine specs are independent of each other. They share only the input data shape via the shared definition.

## Decisions and Rationale

| ID | Decision | Alternatives | Rationale | Affected Specs | Date |
|----|----------|-------------|-----------|----------------|------|
| ARCH-1 | All engine code is pure functions with zero React imports | Allow React hooks in engine | Engine must run in both browser and Node.js CLI. Purity enables easier testing and broader reuse. | traverser, analyzer, mermaid-generator | 2026-03-15 |
| ARCH-2 | Analyzer reimplements traversal internally rather than importing from traverser | Import traverser's `selectOption` for coverage simulation | Keeps specs independent — no cross-spec dependency. Coverage simulation needs different semantics (target-state matching) than user-driven traversal (index-based selection). | analyzer, traverser | 2026-03-15 |
| ARCH-3 | Single shared definition for all schema types | Separate definitions per module (e.g., AnalysisReport definition) | One definition because there's one schema. `AnalysisReport` is analyzer-internal — no other spec consumes it. Adding definitions for internal types would increase governance overhead without traceability benefit. | all | 2026-03-15 |
