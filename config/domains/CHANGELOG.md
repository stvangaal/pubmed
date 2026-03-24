# Domain Config Schema Changelog

Each config YAML carries its own `config_version` field, versioned independently.
The pipeline checks each against `CURRENT_CONFIG_VERSIONS` in `src/config.py`
and logs a WARNING per config if they differ (non-fatal).

Additionally, `domain.yaml` has a `schema_version` field for the domain manifest itself.

When to bump a config's version:
- A new field is added to that config model with **no safe default** (operator must set it explicitly)
- An existing field is **renamed or removed**
- A file path convention changes (e.g. `seen_pmids_file`, `triage_prompt_file`)

When NOT to bump:
- A new field is added with a safe default (old configs silently inherit the default — fine)
- Changes are purely to prompts or prose values
- A different config changed (each config versions independently)

---

## search-config v1 — initial release (2026-03-24)

Initial versioned schema. Fields: `mesh_terms`, `additional_terms`, `date_window_days`,
`api_key`, `retmax`, `require_abstract`, `rate_limit_delay`.

## filter-config v1 — initial release (2026-03-24)

Initial versioned schema. Fields: `rule_filter.*`, `llm_triage.*`, `priority_journals`.
Key domain-scoped fields: `llm_triage.seen_pmids_file`, `llm_triage.triage_prompt_file`.

## summary-config v1 — initial release (2026-03-24)

Initial versioned schema. Fields: `prompt_template_file`, `model`, `max_tokens`,
`subdomain_options`, `feedback_form_url`, `feedback_pmid_field`.

## distribute-config v1 — initial release (2026-03-24)

Initial versioned schema. Fields: `digest_title`, `opening`, `closing`, `sort_by`,
`full_summary_threshold`, `output.file`, `output.plain_text`, `output.plain_text_file`.

## blog-config v1 — initial release (2026-03-24)

Initial versioned schema. Fields: `site_title`, `site_description`, `base_url`,
`publish`, `branch`, `digests_dir`, `closing`, `templates.post`, `templates.index`.

## email-config v1 — initial release (2026-03-24)

Initial versioned schema. Fields: `enabled`, `from_address`, `to_addresses`, `subject`.

## domain.yaml v1 — initial release (2026-03-24)

**Introduced by:** `claude/expand-neurology-search-91lNC`

First versioned domain manifest. Establishes the full domain config layout:

```
config/domains/<domain>/
  domain.yaml               ← schema_version (domain manifest)
  search-config.yaml        ← config_version: 1
  filter-config.yaml        ← config_version: 1
  summary-config.yaml       ← config_version: 1
  distribute-config.yaml    ← config_version: 1
  blog-config.yaml          ← config_version: 1
  email-config.yaml         ← config_version: 1
  prompts/
    triage-prompt.md
    summary-prompt.md
```

**Migration from legacy flat config/:**
No automated migration. Copy `config/` files into `config/domains/<domain>/`, add
`config_version: 1` to each YAML, update `seen_pmids_file`, `triage_prompt_file`,
output paths, and `digests_dir` to be domain-scoped, then add `domain.yaml`
with `schema_version: "1"`.

---

<!-- Add new versions above this line, newest first. -->
