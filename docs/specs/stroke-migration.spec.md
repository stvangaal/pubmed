---
name: stroke-migration
status: draft
owner: infrastructure
disposable: true
owns:
  - config/domains/stroke/domain.yaml
  - config/domains/stroke/search-config.yaml
  - config/domains/stroke/filter-config.yaml
  - config/domains/stroke/summary-config.yaml
  - config/domains/stroke/distribute-config.yaml
  - config/domains/stroke/blog-config.yaml
  - config/domains/stroke/email-config.yaml
  - config/domains/stroke/prompts/triage-prompt.md
  - config/domains/stroke/prompts/summary-prompt.md
requires:
  - name: domain-config
    version: v0
provides: []
---

# Stroke Migration

## Status
draft

## Target Phase
Phase 4

## Purpose

One-time migration of the existing flat `config/` stroke configuration into the domain-scoped layout at `config/domains/stroke/`. This spec is **disposable** — it is deleted after the migration PR merges.

## Requires (Inbound Contracts)

| Dependency | Source | Definition |
|------------|--------|------------|
| Domain config layout | domain-config spec | Convention: `config/domains/{name}/` directory structure |

## Provides (Outbound Contracts)

None. This is a data migration, not a code change.

## Behaviour

### Migration Steps

1. Create `config/domains/stroke/` directory.
2. Copy each flat config file into the domain directory:
   - `config/search-config.yaml` → `config/domains/stroke/search-config.yaml`
   - `config/filter-config.yaml` → `config/domains/stroke/filter-config.yaml`
   - `config/summary-config.yaml` → `config/domains/stroke/summary-config.yaml`
   - `config/distribute-config.yaml` → `config/domains/stroke/distribute-config.yaml`
   - `config/blog-config.yaml` → `config/domains/stroke/blog-config.yaml`
   - `config/email-config.yaml` → `config/domains/stroke/email-config.yaml`
3. Copy prompts:
   - `config/prompts/triage-prompt.md` → `config/domains/stroke/prompts/triage-prompt.md`
   - `config/prompts/summary-prompt.md` → `config/domains/stroke/prompts/summary-prompt.md`
4. Create `config/domains/stroke/domain.yaml` with `schema_version: "1"`.
5. Update domain-scoped paths in the copied configs:
   - `filter-config.yaml`: set `llm_triage.seen_pmids_file` to `data/domains/stroke/seen-pmids.json`
   - `filter-config.yaml`: set `llm_triage.triage_prompt_file` to `config/domains/stroke/prompts/triage-prompt.md`
   - `summary-config.yaml`: set `prompt_template_file` to `config/domains/stroke/prompts/summary-prompt.md`
   - `distribute-config.yaml`: set `output.file` to `output/domains/stroke/digest.md` and `output.plain_text_file` to `output/domains/stroke/digest.txt`
   - `blog-config.yaml`: set `digests_dir` to `digests/stroke`
6. Initialize `data/domains/stroke/` directory (for seen-pmids.json at runtime).
7. **Do NOT delete** the flat `config/*.yaml` files — they remain for backward compatibility.

### GitHub Actions Workflow Update

Update `.github/workflows/weekly-digest.yml`:
- Add matrix strategy with `domain: [stroke]`
- Change pipeline invocation to `python3 -m src.pipeline --domain ${{ matrix.domain }}`
- Update artifact upload to use `output/domains/${{ matrix.domain }}/`
- Set `fail-fast: false` for independent domain failures

### Verification

Run `python3 -m src.pipeline --domain stroke` and compare output against `python3 -m src.pipeline` (legacy). Both should produce functionally identical digests (output paths will differ).

## Decisions

| ID | Decision | Alternatives Considered | Rationale | Date |
|----|----------|------------------------|-----------|------|
| SM1 | Keep flat config files after migration | Delete flat configs; symlink flat to domain | Preserves backward compatibility for anyone running without `--domain`. Can be cleaned up in a future PR when legacy mode is deprecated. | 2026-03-24 |

## Disposal

After the migration PR merges and `--domain stroke` is verified in production:

1. Delete this spec file (`docs/specs/stroke-migration.spec.md`)
2. Remove the `stroke-migration` entry from `REGISTER.md`
3. Optionally delete the flat `config/*.yaml` files if legacy mode is no longer needed
