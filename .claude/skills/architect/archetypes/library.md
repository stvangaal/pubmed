# Archetype: Library

**Based on:** rule-flow-engine (schema traversal library)

## Recognition Signals

- **Keywords:** library, SDK, toolkit, package, module, functions, API surface, consumers, pure
- **Data flow:** consumers call in, get results back — no persistent state transformation
- **Shape:** hub-and-spoke — capabilities radiate from a shared data shape

## Level Model

| Level | What it captures |
|-------|-----------------|
| System | What the library does, who consumes it, platform constraints |
| Spec Group | Capability areas — clusters of specs serving a similar purpose |
| Spec | One independently useful capability operating on the shared data shape |
| Code | files with `# owner: <spec-name>` header |

## Grouping Axis

Functional — groups cluster specs by capability area

## Boundary Pattern

- **Between groups:** shared definitions at the hub, consumed by all capability specs
- **Within groups:** specs are independent — they operate on the shared data shape, not on each other

## Diagram Template

```
              ┌──────────────┐
              │ shared       │
              │ definition   │
              │ (the hub)    │
              └──────┬───────┘
          ┌──────────┼──────────┐
          ▼          ▼          ▼
     ┌─────────┐ ┌────────┐ ┌────────┐
     │ spec A  │ │ spec B │ │ spec C │
     └─────────┘ └────────┘ └────────┘
       GROUP: Engine (or domain name)
```

## Generic Essentials

| Priority | Essential | What to get right |
|----------|-----------|-------------------|
| HIGH COST | The shared data shape at the hub | Every capability spec depends on this definition. Change it and every spec is affected. Get the core types right early. |
| HIGH COST | Capability boundaries | Each spec should be independently useful. If consumers always need spec A and spec B together, they might be one spec. |
| MODERATE | Consumer API surface | What consumers import and call. Internal organization can change; the public API is the commitment. |
| MODERATE | Spec independence | Specs in the same group should not import from each other. If they need shared logic, it belongs in the hub definition or in a new shared spec. |

## Project-Specific Essentials to Look For

- Whether the library has runtime state (if so, it might be closer to a service than a library)
- Whether consumers use capabilities independently or always in combination (affects grouping)
- Platform/environment constraints (browser + Node.js, specific runtimes)

## Spike Triggers

For each HIGH COST essential, recommend a spike:

| Essential | What to spike | Question it answers | Success criteria |
|-----------|--------------|-------------------|-----------------|
| Shared data shape | Build a minimal type definition and write 2-3 functions against it | Does the core type support the operations you need? | Functions work naturally with the type, no awkward workarounds |
| Capability boundaries | Implement one capability end-to-end | Can a consumer use this capability without importing anything else? | The capability is independently useful and testable |

## Architecture.md Template Sections

For library projects, the generated ARCHITECTURE.md should include:

1. System context — what the library does, consumer types, platform constraints
2. Hub diagram — shared definition at center, capability groups radiating out
3. Capability group descriptions — per group: purpose, member specs, consumer-facing API
4. Shared definition — the hub type(s), what they represent, versioning strategy
5. Essentials and recommended spikes
6. Decisions and rationale

### Example (rule-flow-engine)

```
              ┌──────────────────┐
              │  ruleflow-schema │
              │  (definition)    │
              └────────┬─────────┘
          ┌────────────┼────────────┐
          ▼            ▼            ▼
   ┌───────────┐ ┌──────────┐ ┌─────────┐
   │ traverser │ │ analyzer │ │ mermaid │
   └───────────┘ └──────────┘ └─────────┘
         GROUP: Engine

   ┌─────────────────┐ ┌──────────────────┐
   │ project-infra   │ │ test-infra       │
   └─────────────────┘ └──────────────────┘
         GROUP: Infrastructure
```

## Group Document Template Sections

For library projects, each generated group stub should include:

1. Purpose — what capability this group provides
2. Hub definition reference — which shared definition(s) this group operates on
3. Member specs — table of specs with one-line responsibilities
4. Consumer API surface — what consumers import from this group
5. Independence — how specs in this group avoid lateral dependencies
6. Decisions — group-level architectural decisions
