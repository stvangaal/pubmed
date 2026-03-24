# Domain Config Schema Changelog

Each domain directory contains a `domain.yaml` with a `schema_version` field.
The pipeline checks this against `CURRENT_DOMAIN_SCHEMA_VERSION` in `src/config.py`
and logs a warning if they differ.

When to bump the schema version:
- A new field is added to a config model with **no safe default** (operator must set it explicitly)
- An existing field is **renamed or removed**
- A file path convention changes (e.g. `seen_pmids_file`, `triage_prompt_file`)

When NOT to bump:
- A new field is added with a safe default (old configs silently inherit the default — fine)
- Changes are purely to prompts or prose values

---

## Version 1 — initial release (2026-03-24)

**Introduced by:** `claude/expand-neurology-search-91lNC`

First versioned schema. Establishes the full domain config layout:

```
config/domains/<domain>/
  domain.yaml               ← schema_version + domain manifest
  search-config.yaml
  filter-config.yaml        ← includes llm_triage.seen_pmids_file (per-domain dedup)
  summary-config.yaml       ← includes prompt_template_file pointing to domain prompts
  distribute-config.yaml    ← includes output.file under output/domains/<domain>/
  blog-config.yaml          ← includes digests_dir: digests/<domain>
  email-config.yaml
  prompts/
    triage-prompt.md
    summary-prompt.md
```

**Key fields introduced in v1 (not present in legacy flat config/):**
- `llm_triage.seen_pmids_file` — per-domain dedup history path
- `domain.yaml` manifest itself

**Migration from legacy flat config/:**
No automated migration. Copy `config/` files into `config/domains/<domain>/`, update
`seen_pmids_file`, `triage_prompt_file`, output paths, and `digests_dir` to be
domain-scoped, then add `domain.yaml` with `schema_version: "1"`.

---

<!-- Add new versions above this line, newest first. -->
