# Project Register

## Definitions Index

| Definition | Version | Status | Primary Implementor | Required By |
|------------|---------|--------|---------------------|-------------|
| `definitions/ruleflow-schema.md` | v1 | stable | traverser | traverser, analyzer, mermaid-generator |

## Spec Index

| Spec | Phase | Status | Owns (files/directories) | Depends On |
|------|-------|--------|--------------------------|------------|
| project-infrastructure | 0 | implemented | *(project config — out of sample scope)* | test-infrastructure |
| test-infrastructure | 0 | implemented | *(test config — out of sample scope)* | — |
| traverser | 1 | implemented | `src/engine/types.ts`, `src/engine/traverser.ts` | `definitions/ruleflow-schema.md@v1` |
| analyzer | 1 | implemented | `src/engine/analyzer/` | `definitions/ruleflow-schema.md@v1` |
| mermaid-generator | 1 | implemented | `src/engine/mermaid.ts` | `definitions/ruleflow-schema.md@v1` |

## Phase Summary

| Phase | Specs (count) | Status |
|-------|--------------|--------|
| 0 | 2 | implemented |
| 1 | 3 | implemented |

## Unowned Code
<!-- This section should always be empty -->

*(empty — all source files are assigned to a spec)*

## Dependency Resolution Order

### Phase 0
1. test-infrastructure
2. project-infrastructure (depends on test-infrastructure's entry point)

### Phase 1
1. traverser, analyzer, mermaid-generator (all independent — can be implemented in any order)

Note: All three Phase 1 specs depend on `definitions/ruleflow-schema.md@v1` but not on each other. The dependency graph is a hub-and-spoke with the shared definition at the center.
