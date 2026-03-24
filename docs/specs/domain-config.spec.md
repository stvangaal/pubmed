---
name: domain-config
status: draft
owner: infrastructure
owns:
  - config/domains/_template/domain.yaml
  - config/domains/_template/search-config.yaml
  - config/domains/_template/filter-config.yaml
  - config/domains/_template/summary-config.yaml
  - config/domains/_template/distribute-config.yaml
  - config/domains/_template/blog-config.yaml
  - config/domains/_template/email-config.yaml
  - config/domains/_template/prompts/triage-prompt.md
  - config/domains/_template/prompts/summary-prompt.md
  - config/domains/CHANGELOG.md
  - tests/test_domain_config.py
requires: []
provides: []
---

# Domain Config

## Status
draft

## Target Phase
Phase 4

## Purpose

Define the domain-scoped configuration layout that enables the pipeline to support multiple clinical domains (stroke, neurology, etc.) with isolated config packages. Each domain is a self-contained directory under `config/domains/{name}/` that can be created by copying `_template/` and filling in domain-specific values.

This spec owns the **layout and templates** — not the config loading code itself (which belongs to `project-infrastructure`).

## Requires (Inbound Contracts)

None. This spec defines a file convention, not a code dependency.

## Provides (Outbound Contracts)

| Export | Type | Definition |
|--------|------|------------|
| Domain config directory layout | convention | No formal definition — convention documented here |

## Behaviour

### Domain Directory Layout

Each domain is a directory under `config/domains/` containing:

```
config/domains/{name}/
  domain.yaml               ← schema version manifest
  search-config.yaml        ← PubMed query terms (MeSH, date window)
  filter-config.yaml        ← article type rules, LLM triage settings, seen_pmids_file
  summary-config.yaml       ← subdomain taxonomy, prompt path, model settings
  distribute-config.yaml    ← digest title, output paths
  blog-config.yaml          ← site title, digests_dir, template overrides
  email-config.yaml         ← sender, recipients, subject
  prompts/
    triage-prompt.md        ← domain-specific LLM triage prompt
    summary-prompt.md       ← domain-specific LLM summary prompt
```

### Template Directory

`config/domains/_template/` contains all files with TODO placeholders for domain-specific values. Onboarding a new domain:

1. Copy `_template/` to `config/domains/{new-domain}/`
2. Fill in all TODO fields
3. Write domain-specific triage and summary prompts
4. Create `data/domains/{new-domain}/` for runtime data (seen-pmids, etc.)
5. Add the domain to the GitHub Actions workflow matrix

No code changes are required to add a domain.

### Schema Versioning

Each domain directory contains a `domain.yaml` manifest with a `schema_version` field. The pipeline checks this against `CURRENT_DOMAIN_SCHEMA_VERSION` in `src/config.py`:

- **Match:** pipeline proceeds normally
- **Mismatch:** pipeline logs a WARNING and proceeds (non-fatal)
- **Missing `domain.yaml`:** pipeline logs a WARNING and proceeds

When to bump `CURRENT_DOMAIN_SCHEMA_VERSION`:
- A new field is added to a config model with **no safe default** (operator must set it explicitly)
- An existing field is renamed or removed
- A file path convention changes

When NOT to bump:
- A new field is added with a safe default (old configs silently inherit it)
- Changes are purely to prompt text or prose values

### Change History

`config/domains/CHANGELOG.md` documents all schema versions with:
- What changed
- Which branch introduced it
- Migration instructions for existing domain directories

Single file for all config schemas — keeps the history in one reviewable place.

### Global vs Domain-Scoped Config

| Setting | Scope | Location |
|---------|-------|----------|
| API keys (ANTHROPIC_API_KEY, RESEND_API_KEY, NCBI_API_KEY) | Global | Environment variables |
| Rate limits (rate_limit_delay) | Per-domain config (but typically identical) | `search-config.yaml` |
| Blog templates (blog-post.md, blog-index.md) | Global default, domain-overridable | `config/templates/` (default), `blog-config.yaml` `templates.post`/`templates.index` (override) |
| All other config | Per-domain | `config/domains/{name}/` |

### Config Resolution (implemented by project-infrastructure)

When `--domain` is specified:
- `_config_path(filename, domain)` returns `config/domains/{domain}/{filename}`

When `--domain` is omitted (legacy mode):
- `_config_path(filename, None)` returns `config/{filename}`

This dual-path approach maintains backward compatibility with the flat layout.

## Decisions

| ID | Decision | Alternatives Considered | Rationale | Date |
|----|----------|------------------------|-----------|------|
| DC1 | One directory per domain with all configs co-located | Config-type directories (all search configs together); single file with domain sections | Co-location makes each domain self-contained and copyable. An operator can understand one domain by reading one directory. | 2026-03-24 |
| DC2 | Schema version in YAML manifest, not in each config file | Version in each YAML; version in filename; database-tracked versions | Single manifest per domain is the simplest model. One field to check, one file to update per domain. | 2026-03-24 |
| DC3 | Single CHANGELOG.md for all config schemas | One changelog per config file; inline in YAML comments | Single file is easiest to review in PRs and gives a complete migration picture. | 2026-03-24 |
| DC4 | Advisory warnings on version mismatch, not errors | Hard error blocking pipeline; silent ignore | Operators should not be blocked by a version drift that may be intentional (e.g., testing a new field). Warnings surface in CI logs for review. | 2026-03-24 |

## Tests

### Unit Tests

- **test_template_completeness**: Verify `_template/` contains all 7 YAML files and both prompt files.
- **test_template_has_todos**: Verify every template file contains at least one TODO marker.
- **test_domain_yaml_schema_version**: Verify `_template/domain.yaml` has `schema_version: "1"`.
- **test_changelog_documents_version_1**: Verify `CHANGELOG.md` contains a "Version 1" section.

### Contract Tests

- **test_config_path_domain**: Verify `_config_path("search-config.yaml", "stroke")` returns `config/domains/stroke/search-config.yaml`.
- **test_config_path_legacy**: Verify `_config_path("search-config.yaml", None)` returns `config/search-config.yaml`.
- **test_schema_check_match**: Verify `check_domain_schema()` logs no warning when versions match.
- **test_schema_check_mismatch**: Verify `check_domain_schema()` logs a WARNING when versions differ.
- **test_schema_check_missing_manifest**: Verify `check_domain_schema()` logs a WARNING when `domain.yaml` is absent.
