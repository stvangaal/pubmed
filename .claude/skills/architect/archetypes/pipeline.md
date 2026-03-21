# Archetype: Pipeline

**Based on:** arbutus (physician billing system)

## Recognition Signals

- **Keywords:** processes, transforms, stages, pipeline, ingests, batch, status progression, workflow
- **Data flow:** linear, sequential — data enters, gets transformed through stages, exits
- **Shape:** `[input] → stage → stage → stage → [output]`

## Level Model

| Level | What it captures |
|-------|-----------------|
| System | What enters the system, what exits, external actors that feed or consume data |
| Spec Group | One group per transformation stage — each stage advances the core domain object to a new status |
| Spec | One spec per distinct operation within a stage — each spec transforms or validates the domain object |
| Code | files with `# owner: <spec-name>` header |

## Grouping Axis

Temporal — groups follow data transformation stages

## Boundary Pattern

- **Between groups:** shared definition with status qualifier (e.g., `BillableActivity@assigned`)
- **Within groups:** specs share definitions, no lateral imports between specs

## Diagram Template

```
[input] → GROUP₁ → GROUP₂ → GROUP₃ → [output]
           │specs│   │specs│   │specs│
                      ▲
                 definitions
                 (flowing + config)
```

## Generic Essentials

| Priority | Essential | What to get right |
|----------|-----------|-------------------|
| HIGH COST | Core domain object | The thing flowing through all stages — its shape and status progression are the pipeline's spine. Change this and every stage is affected. |
| HIGH COST | Stage ordering | Which stages depend on decisions (not just data) from prior stages. Getting the order wrong means redesigning multiple stages. |
| MODERATE | Group boundaries | Named definition + status at every arrow in the diagram. If you can't name the boundary, it isn't clean. |
| MODERATE | Spec independence within groups | Specs in the same group depend on shared definitions, not on each other. If spec A imports from spec B within the same group, they should be one spec or in different groups. |

## Project-Specific Essentials to Look For

- Human decision points that should be modeled as stages, not side-channels
- Configuration definitions (read by many stages) vs. flowing definitions (transformed by stages) — these have different change patterns
- External system integrations that constrain stage ordering

## Spike Triggers

For each HIGH COST essential, recommend a spike:

| Essential | What to spike | Question it answers | Success criteria |
|-----------|--------------|-------------------|-----------------|
| Core domain object | Test the core type and status progression against real data | Does the status progression actually work for real inputs? | Real data flows through all statuses without forcing or skipping |
| Stage ordering | Spike with representative inputs through the first 2-3 stages | Do earlier decisions actually need to precede later stages? | Later stages demonstrably need outputs/decisions from earlier ones |
| Human decision points | Mock the review interface with sample data | What information do reviewers actually need to see? | Reviewers can make decisions from the mockup without asking for more data |

## Architecture.md Template Sections

For pipeline projects, the generated ARCHITECTURE.md should include:

1. System context — what enters (data sources), what exits (outputs), external actors
2. Pipeline diagram — groups as boxes, specs listed inside, definition + status on arrows between groups
3. Stage descriptions table — per group: purpose, input status, output status, member specs
4. Shared definitions — categorized as: flowing (transformed by stages), config (read by many stages), reference (lookup data)
5. Essentials and recommended spikes
6. Decisions and rationale

### Example (arbutus)

```
  ClinicalDocument          BillableActivity        BillableActivity           Claim                 Claim
    (from EHR)                 @assigned               @enriched             @generated             @exported
        │                         │                       │                      │                      │
        ▼                         ▼                       ▼                      ▼                      ▼
┌───────────────┐        ┌─────────────────┐      ┌──────────────┐      ┌───────────────┐      ┌────────────┐
│ INGESTION &   │───────▶│ EXTRACTION &    │─────▶│ CLAIM        │─────▶│ QUALITY &     │─────▶│ OUTPUT     │
│ ROUTING       │        │ CLASSIFICATION  │      │ PRODUCTION   │      │ VALIDATION    │      │            │
│               │        │                 │      │              │      │               │      │            │
│ • ingestion   │        │ • llm-extract   │      │ • rules-     │      │ • claim-      │      │ • export   │
│ • contract-   │        │ • classify      │      │   engine     │      │   validation  │      │            │
│   assignment  │        │ • enrichment    │      │ • claim-     │      │ • review-     │      │            │
│ • query-      │        │ • time-overlap  │      │   generation │      │   interface   │      │            │
│   interface   │        │                 │      │              │      │               │      │            │
└───────────────┘        └─────────────────┘      └──────────────┘      └───────────────┘      └────────────┘
        ▲                         ▲                       ▲
   ┌────┴──────┐          ┌───────┴───────┐        ┌─────┴──────┐
   │ specialty │          │ extracted-    │        │ fee-code-  │
   │ config    │          │ data          │        │ mapping    │
   │ document- │          │ on-call-      │        │            │
   │ space     │          │ schedule      │        │            │
   └───────────┘          └───────────────┘        └────────────┘
     CONFIG                 REFERENCE                REFERENCE
```

## Group Document Template Sections

For pipeline projects, each generated group stub should include:

1. Purpose — what transformation this stage performs
2. Input — definition name + status qualifier (e.g., BillableActivity@assigned)
3. Output — definition name + status qualifier (e.g., BillableActivity@enriched)
4. Member specs — table of specs in this group with one-line responsibilities
5. Internal structure — ordering of specs within the stage (if any)
6. Boundary definitions — which definitions this group reads/writes
7. Decisions — group-level architectural decisions
