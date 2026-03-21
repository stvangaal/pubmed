# RuleFlow Engine — Walkthrough

## Introduction

Arboretum is a spec-driven development workflow where humans architect and AI implements within documented boundaries. Every line of code is owned by a specification, shared data structures are defined once and versioned, and staleness is detected mechanically rather than by memory. The human writes the design intent — purpose, behaviour, decisions — and the AI fills in traceability structure and produces code that satisfies it.

RuleFlow is a TypeScript framework for converting business rules into interactive decision tree wizards. The engine layer is the pure-logic core: a traverser that walks schemas step-by-step, an analyzer that validates them for structural errors and logic gaps, and a mermaid generator that renders them as flowcharts. No UI, no build tools, no framework dependencies. It runs in both the browser and Node.js.

This sample project demonstrates every arboretum governance artifact applied to that engine layer. The code is real. The governance documents — architecture, shared definitions, specs, register, version pins — are what you would produce if you built it using arboretum. Together they show what "done" looks like: a project where every source file traces to a spec, every spec traces to the architecture, and version pins catch drift automatically.

You can follow the sections in order for the narrative (each builds on the last), or jump to any file and use this guide as a reference. File paths throughout are relative to this `examples/rule-flow-engine/` directory.

## Step 1 — Architecture

The architecture document is the first thing you write because it is the first thing the AI reads. At the start of every session, the AI consults the architecture to orient itself — which components exist, how they relate to each other, what cross-cutting decisions have already been settled. Without it, the AI reinvents structure from scratch each time, making inconsistent choices across sessions.

Open `docs/ARCHITECTURE.md`. It describes three engine components:

- **Traverser** — pure state machine for step-by-step schema traversal
- **Analyzer** — schema validator producing structured analysis reports
- **Mermaid Generator** — converts schemas into Mermaid flowchart strings

Each has a one-line responsibility statement and a reference to its spec file. Below the component list, the dependency graph shows the shape of the system:

```
definitions/ruleflow-schema.md@v1
    ├── traverser.spec (primary implementor + consumer)
    ├── analyzer.spec (consumer)
    └── mermaid-generator.spec (consumer)
```

This is a hub-and-spoke topology. All three engine modules depend on the shared type definition, but none depend on each other. That independence is a deliberate architectural choice — it means any module can be implemented, tested, and changed without touching the others.

Notice the size of the document: it is a map, not a manual. The `~5,000 word` size cap in `SPEC-WORKFLOW.md` exists because architecture should orient, not exhaustively specify. Detailed behaviour belongs in individual specs.

Now look at the Decisions table at the bottom. Cross-cutting decisions live here rather than in individual specs. ARCH-2, for example, records that the analyzer reimplements traversal internally rather than importing from the traverser module. This keeps the two specs independent. By recording the decision and its rationale in the architecture, you prevent it from being relitigated in multiple places — anyone reading either spec can trace back to the architectural reasoning.

## Step 2 — Shared Definitions

Here is the moment that makes shared definitions worth the overhead. All three engine modules import from `types.ts`. If each spec described these types independently — the traverser spec defining `RuleFlowSchema` one way, the analyzer spec defining it slightly differently — they could silently diverge. One spec adds a field, another does not know about it, and the AI implements two incompatible versions of the same type. Shared definitions prevent that by establishing a single canonical source.

Open `docs/definitions/ruleflow-schema.md`. The Schema section contains the full TypeScript type hierarchy: variables (enum and boolean), goto targets (simple strings and conditional objects), options, nodes, results, metadata, display theming, and the top-level `RuleFlowSchema` interface that ties them all together. This is the contract. Every module that consumes these types agrees to this shape.

Below the schema, the Constraints section records rules that all consumers must respect: node and result IDs must be `snake_case`, goto targets use the `result:` prefix to distinguish terminals from question nodes, variables must be declared before use, and every path from `start_node` must reach a terminal. These constraints exist in the definition rather than in any single spec because they apply across all three modules.

Now look at the version header: `v1`. Version numbering follows a simple protocol. During early development, a definition starts at `v0` — free to change without ceremony. Once the types are settled and specs have been implemented against them, the definition moves to `v1`. From that point, every change is breaking. All consuming specs must review the change, update their Requires tables, and re-pin. You cannot silently change a `v1` definition; the version bump forces coordination.

The Changelog at the bottom records which specs are affected by each version change. When `v2` eventually happens, you will know exactly which specs need updating — not from memory, but from the document itself.

## Step 3 — Writing Specs

Specs are where the detailed design lives. Each one is a contract between the human (who writes the design intent) and the AI (who implements it). Let's walk through the traverser spec in detail, then briefly cover the other two.

### The traverser spec

Open `docs/specs/traverser.spec.md`.

**Purpose** is a one-to-three sentence statement the human writes. It says what this unit does and why it exists as a separate component. The traverser's purpose: "Pure state machine that walks a RuleFlow schema step-by-step, producing an immutable state at each transition." Short, precise, and scoped.

**Requires/Provides** tables declare the module's boundaries. Requires lists inbound dependencies — here, just the shared `RuleFlowSchema` types at `definitions/ruleflow-schema.md@v1`. Provides lists everything the module exports: nine functions (`createInitialState`, `selectOption`, `goBack`, `getCurrentNode`, `getCurrentResult`, `getSupplementaryResults`, `isComplete`, `canGoBack`, `estimateProgress`) and two types (`TraverserState`, `HistoryEntry`). Every export maps to a row in the Provides table. If something is not listed here, it is an internal implementation detail and must not be exported. The AI derives these tables from the Behaviour section and the shared definitions — the human reviews them for accuracy.

**Behaviour** is the core of the spec, and the human writes it. It must be detailed enough that the AI can implement without asking questions. The traverser's Behaviour section covers:

- **State shape** — the six fields of `TraverserState` and what each one holds
- **Initialization** — what `createInitialState` returns
- **Forward traversal** — the ten-step process for `selectOption`, including variable assignment, history recording, goto resolution, and terminal detection
- **Goto resolution** — how simple string gotos and conditional gotos are evaluated
- **Back navigation** — how `goBack` replays history to rebuild variable state
- **Accessors** — what the lookup functions return
- **Progress estimation** — full DFS enumeration of paths to compute average depth

Each subsection tells the AI exactly what to build. No guessing, no inventing.

**Decisions** record spec-scoped choices with rationale. The traverser has three: immutable state (TR1), full history replay for goBack (TR2), and DFS for progress estimation (TR3). Each row includes alternatives that were considered and the reasoning for the chosen approach. Recording the alternatives is important — it prevents relitigating settled questions in future sessions.

**Tests** are organized into three tiers. Unit tests list eleven specific checks against a minimal 3-node schema. Contract tests verify that the `TraverserState` shape matches the Provides table — all six fields present with correct types. Integration tests are marked N/A with a reason: no cross-spec dependencies exist. Each tier is either filled in or explicitly marked N/A. There is no ambiguity about what testing is expected.

### The analyzer spec

Open `docs/specs/analyzer.spec.md`. Same structure, different content. The Behaviour section defines a three-tier checking pipeline: structural errors (invalid graph structure), logic warnings (coverage gaps detected via state-space simulation), and style info (UX improvement suggestions). Decision A1 is worth noting: the analyzer reimplements traversal internally rather than importing from the traverser. This mirrors the architectural decision ARCH-2. By recording it in both places — the architecture for the cross-cutting rationale, the spec for the local implementation guidance — the AI has the context it needs regardless of which document it reads first. Integration tests are N/A because this decision eliminated the only potential cross-spec dependency.

### The mermaid generator spec

Open `docs/specs/mermaid-generator.spec.md`. The simplest of the three. Two exports (`generateMermaid` and `MermaidOptions`), BFS traversal with depth limiting, label truncation and escaping rules, and category-based result coloring. Same shared definition dependency, same N/A pattern for integration tests.

### The collaborative authoring model

Across all three specs, notice the division of labour. The human writes Purpose and Behaviour — the parts that require domain knowledge and architectural judgment. The AI fills Requires/Provides tables (deriving them from Behaviour and the shared definitions), translates test descriptions into executable tests, and handles the mechanical traceability structure. The human reviews and approves before implementation begins. This splits the work at the right seam: humans own *what* and *why*, the AI handles *traceability* and *structure*.

## Step 4 — The Register

The register is the single lookup table that answers two questions at a glance: "where does this live?" and "what depends on what?"

Open `docs/REGISTER.md`. It has four sections.

**Definitions Index** lists each shared definition, its current version, its primary implementor, and which specs require it. In this project there is one definition (`definitions/ruleflow-schema.md` at `v1`), the traverser is the primary implementor (meaning its code in `types.ts` is the canonical TypeScript expression of the definition), and all three engine specs consume it.

**Spec Index** lists each spec with its phase, status, the files it owns, and what it depends on. The traverser owns `src/engine/types.ts` and `src/engine/traverser.ts`. The analyzer owns the entire `src/engine/analyzer/` directory. The mermaid generator owns `src/engine/mermaid.ts`. Every source file maps to exactly one spec.

**Dependency Resolution Order** tells you the implementation sequence. Phase 0 first: test-infrastructure (no dependencies), then project-infrastructure (depends on test-infrastructure's entry point). Phase 1 next: all three engine specs in any order, since they are independent. This ordering is not a suggestion — it is the sequence that guarantees each spec's dependencies are satisfied before it starts.

**Unowned Code** should always be empty. If a source file exists on disk that no spec claims in the Owns column, something needs to be assigned or deleted. In this project, it is empty — all source files are accounted for.

The register also describes a five-step audit process for detecting staleness: (1) every file listed in the register exists on disk, (2) every source file on disk appears in exactly one spec's Owns column, (3) version pins in the register match the definition headers, (4) dependency links match specs' Requires tables, (5) report discrepancies. This is how staleness is detected mechanically — by cross-referencing documents and files, not by hoping someone remembers what changed.

## Step 5 — Version Pins

Open `contracts.yaml`. This small YAML file is the machine-readable expression of which spec depends on which definition version. Three places must agree on definition versions:

1. **The definition's `## Version` header** — the canonical source (`definitions/ruleflow-schema.md` says `v1`)
2. **Each spec's Requires/Provides tables** — the human-readable pins (all three specs say `definitions/ruleflow-schema.md@v1`)
3. **`contracts.yaml`** — the machine-readable pins that contract tests read at runtime

Why the redundancy? Because contract tests use `contracts.yaml` to verify at runtime that code still conforms to the pinned definition version. When a definition bumps from `v1` to `v2`, contract tests for specs still pinned to `v1` fail automatically. You cannot forget to update consuming specs — the test suite catches it for you.

Look at the traverser's entry. It has both a `requires` key and a `provides` key for the same definition. That `provides` key marks it as the primary implementor — its code (`types.ts`) is the canonical TypeScript expression of the definition. The analyzer and mermaid-generator only have `requires` keys because they consume the types without implementing them.

The three-sync-point design is an accepted tradeoff: more places to update when a version changes, but mechanical detection of drift when someone misses one. In practice, the AI handles the updates across all three locations; the three-way check catches the mistakes. One source of truth would be simpler, but it would not catch the case where a spec's Requires table says `v1` while the definition has moved to `v2`.

## Step 6 — Implementation

Once specs are written and approved, the AI derives its implementation context automatically. It reads the architecture document for orientation, then the target spec for detailed requirements, then all definitions referenced in the spec's Requires table for type contracts, and finally the implementations of any specs listed as dependencies. No extra instructions needed — the governance documents *are* the instructions.

Implementation follows TDD: write failing tests from the spec's Tests section, implement to make them pass, tier by tier. Unit tests first (always required), contract tests next (when shared definitions are referenced), integration tests last (when cross-spec dependencies exist).

The source code in `src/engine/` is the result of this process. Browse it alongside the specs and you will see the traceability: every Provides entry maps to an export in the source file, every Behaviour paragraph maps to a function or code block, and every test described in the spec maps to a check the test suite would run. The traverser spec's ten-step `selectOption` process, for example, maps directly to the implementation in `src/engine/traverser.ts`.

This sample focuses on governance documents and source code; it does not include the test files themselves. But the specs define precisely what tests would verify, at what tier, and against what fixtures.

## What You've Seen

Here is a recap of every artifact in this sample and how it maps to the arboretum workflow:

| Sample Artifact | Arboretum Concept | SPEC-WORKFLOW.md Reference |
|-----------------|-----------------|---------------------------|
| `docs/ARCHITECTURE.md` | Architecture document | Section 3 |
| `docs/definitions/ruleflow-schema.md` | Shared definition | Section 1 |
| `docs/specs/traverser.spec.md` | Specification | Section 2 |
| `docs/specs/analyzer.spec.md` | Specification | Section 2 |
| `docs/specs/mermaid-generator.spec.md` | Specification | Section 2 |
| `docs/REGISTER.md` | Project register | Section 4 |
| `contracts.yaml` | Version pins | Section 1 |
| `docs/specs/test-infrastructure.spec.md` | Reserved spec | Section 5 |
| `docs/specs/project-infrastructure.spec.md` | Reserved spec | Section 5 |

Arboretum adds upfront documentation cost. You write an architecture document before any code. You define shared types in a versioned definition before any spec references them. You write specs with detailed behaviour sections before asking the AI to implement anything. That is real overhead.

The payoff is threefold. First, **traceability**: every line of code traces to a spec, every spec traces to the architecture, every shared type traces to a definition. When something breaks, you know where to look. Second, **staleness detection**: version pins and the register audit catch drift automatically. When a definition changes, contract tests for specs still pinned to the old version fail. When a file exists that no spec owns, the register audit flags it. You do not need to remember what changed — the system tells you. Third, **clear boundaries for AI implementation**: the AI knows what to build (the Behaviour section), what not to invent (anything not in the spec), and when to stop and ask (when a spec is ambiguous or infeasible). The documents are the architecture. The code is the expression of it.
