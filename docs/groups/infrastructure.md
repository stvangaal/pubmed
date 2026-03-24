# owner: architecture
---
name: infrastructure
owner: architecture
---

# Infrastructure

## Purpose

Cross-cutting project infrastructure that supports the pipeline but is not itself a pipeline stage. Owns configuration loading, domain resolution, schema versioning, data models, and the pipeline orchestrator.

## Boundaries

**Input:** Domain selection (`--domain` CLI arg), YAML config files, environment variables

**Output:** Resolved configuration objects consumed by all pipeline stages

## Member Specs

| Spec | Responsibility |
|------|---------------|
| project-infrastructure | Core data models (`src/models.py`), config loading (`src/config.py`), pipeline orchestrator (`src/pipeline.py`) |
| domain-config | Domain-scoped config layout (`config/domains/`), `_template/` directory, schema versioning (`domain.yaml`), change history (`CHANGELOG.md`) |

## Internal Structure

`project-infrastructure` owns the code that loads and resolves configs. `domain-config` owns the config layout, templates, and versioning convention. The boundary: code lives with project-infrastructure, config structure lives with domain-config.

## Boundary Definitions

| Definition | Access |
|------------|--------|
| `search-config` | reads (loads from flat or domain-scoped path) |
| `filter-config` | reads (loads from flat or domain-scoped path) |
| `summary-config` | reads (loads from flat or domain-scoped path) |
| `distribute-config` | reads (loads from flat or domain-scoped path) |
| `blog-config` | reads (loads from flat or domain-scoped path) |
| `email-config` | reads (loads from flat or domain-scoped path) |

## Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| I1 | Domain-scoped config is a directory layout concern, not a code abstraction. Each domain is a self-contained directory that can be copied from `_template/`. | Keeps onboarding mechanical — no code changes needed to add a domain, just copy and fill config files. |
| I2 | Schema versioning is advisory (WARNING log), not enforced. Pipeline proceeds even on mismatch. | Operators should not be blocked by a version drift that may be intentional. Warnings surface in CI logs for review. |
