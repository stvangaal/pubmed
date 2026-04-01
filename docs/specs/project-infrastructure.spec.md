---
name: project-infrastructure
status: draft
owner: system
owns:
  - src/__init__.py
  - tests/__init__.py
  - src/models.py
  - src/config.py
  - src/pipeline.py
  - requirements.txt
  - .gitignore
requires: []
provides: []
---

# Project Infrastructure

## Status
draft

## Target Phase
Phase 0

## Purpose
Provide the foundational code that all pipeline stages depend on: shared data models, configuration loading, and the pipeline orchestrator. This spec owns the "glue" — the dataclasses, config parsers, and CLI entry point that tie the four pipeline stages together.

## Requires (Inbound Contracts)
None — this is the base layer of the project.

## Provides (Outbound Contracts)

| Export | Type | Definition |
|--------|------|------------|
| Shared dataclasses | code | `PubmedRecord`, `LiteratureSummary`, `EmailDigest`, config models |
| Config loaders | code | `load_search_config`, `load_filter_config`, `load_summary_config`, etc. |
| Pipeline orchestrator | code | `run()` — CLI entry point that chains all stages |

## Behaviour

### Data Models (`src/models.py`)

Defines all dataclasses used across the pipeline:

- **Domain objects:** `PubmedRecord`, `LiteratureSummary`, `EmailDigest`, `BlogPage`
- **Config objects:** `SearchConfig`, `FilterConfig`, `RuleFilterConfig`, `LLMTriageConfig`, `SummaryConfig`, `DistributeConfig`, `OutputConfig`, `BlogConfig`, `BlogTemplatesConfig`, `EmailConfig`
- **Utility:** `LLMUsage` (token tracking with cost estimation), `Topic` (named search topic)

Each dataclass mirrors a definition in `docs/definitions/`. The models are the Python representation of the shared contracts.

### Configuration Loading (`src/config.py`)

Provides `load_*_config()` functions for each config type. Supports two layouts:

1. **Legacy flat:** `config/{name}.yaml`
2. **Domain-scoped:** `config/domains/{domain}/{name}.yaml`

Includes per-config version checking (`config_version` field) with non-fatal warnings on mismatch. Domain schema validation via `check_domain_schema()`.

### Pipeline Orchestrator (`src/pipeline.py`)

Runs the full pipeline end-to-end via `run()`:

1. Parse `--domain` CLI argument
2. Load all configs
3. Search → Rule filter → LLM triage → Summarize → Blog publish → Digest build → Email send → Troubleshooting report
4. Log progress and costs at each stage
5. Handle empty result sets gracefully (generate empty digest)

### Package Init Files

`src/__init__.py` and `tests/__init__.py` are empty package markers. Each subpackage `__init__.py` is owned by its respective spec.

## Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| PI-1 | Dataclasses over Pydantic | Minimal dependencies; validation happens at system boundaries (config loading, API responses), not internal passing |
| PI-2 | YAML config with version field | Human-readable, diff-friendly; version field enables forward-compatible schema migration |
| PI-3 | Single `run()` orchestrator | Linear pipeline has no branching; a single function is clear and debuggable |
