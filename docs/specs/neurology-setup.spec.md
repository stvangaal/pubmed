---
name: neurology-setup
status: draft
owner: system
owns:
  - config/domains/neurology/domain.yaml
  - config/domains/neurology/search-config.yaml
  - config/domains/neurology/filter-config.yaml
  - config/domains/neurology/summary-config.yaml
  - config/domains/neurology/distribute-config.yaml
  - config/domains/neurology/blog-config.yaml
  - config/domains/neurology/email-config.yaml
  - config/domains/neurology/prompts/triage-prompt.md
  - config/domains/neurology/prompts/summary-prompt.md
requires:
  - name: domain-config
    version: v0
provides: []
---

# Neurology Domain Setup

## Status
draft

## Target Phase
Phase 4

## Purpose
Configure the neurology clinical domain as a config package under `config/domains/neurology/`. Follows the same structure established by `domain-config` and `stroke-migration` — isolated config, prompts, and output paths scoped to the neurology domain.

## Requires (Inbound Contracts)

| Dependency | Source | Definition |
|------------|--------|------------|
| Domain config layout | domain-config | Directory structure and schema versioning conventions |

## Provides (Outbound Contracts)
None — this spec produces configuration files consumed by the pipeline at runtime.

## Behaviour

Uses the domain-config template (`config/domains/_template/`) to create a neurology-specific config package. All paths (seen PMIDs, output files, digests directory, prompt files) are scoped to the neurology domain.

Added to the GitHub Actions workflow matrix (`weekly-digest.yml`) for automated weekly runs alongside stroke.

## Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| NS-1 | Follow stroke-migration pattern exactly | Consistency across domains; proven structure |
