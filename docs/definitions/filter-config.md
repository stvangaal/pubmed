# Filter Config

## Status
draft

## Version
v0

## Description
User-facing configuration for the filter stage. Controls rule-based filtering criteria and LLM triage settings. Users edit this as a YAML file without touching source code. The config is split into two sections: `rule_filter` (deterministic, free) and `llm_triage` (LLM-powered, costs tokens).

## Schema

```yaml
# config/filter-config.yaml

rule_filter:
  # Article types to include (PubMed publication type vocabulary, lowercase)
  include_article_types:
    - randomized controlled trial
    - meta-analysis
    - systematic review
    - practice guideline
    - guideline
    - clinical trial
    - clinical trial, phase iii
    - clinical trial, phase iv
    - multicenter study
    - observational study
    - comparative study

  # Article types to exclude (excluded only if no include type is also present)
  exclude_article_types:
    - case reports
    - letter
    - editorial
    - comment
    - news
    - biography
    - historical article
    - published erratum
    - retraction of publication
    - retracted publication

  # MeSH terms that indicate non-human studies (excluded unless "Humans" is also present)
  exclude_mesh_terms:
    - animals
    - mice
    - rats
    - disease models, animal
    - in vitro techniques

  # Language filter
  require_language: eng

  # Require abstract (articles without abstracts are excluded)
  require_abstract: true

llm_triage:
  # LLM model for triage scoring
  model: claude-sonnet-4-6

  # Maximum tokens for LLM response
  max_tokens: 150

  # Score threshold: articles scoring >= this value are included in the digest
  score_threshold: 0.70

  # Maximum articles to include per run (cap for busy weeks)
  max_articles: 10

  # Minimum articles to include per run (backfill from below-threshold on slow weeks)
  # Default 0 = disabled (no backfill guarantee)
  min_articles: 0

  # Score floor for backfill eligibility (never backfill articles below this score)
  # Default 0.50 = aligns with the "Incremental" tier in scoring guides
  min_score_floor: 0.50

  # Enable prompt caching (reduces cost for repeated system prompt)
  use_prompt_caching: true

  # Path to the triage prompt file (system prompt for LLM scoring)
  triage_prompt_file: config/prompts/triage-prompt.md

  # Path to per-domain dedup history (tracks previously seen PMIDs)
  seen_pmids_file: data/seen-pmids.json

# Journals used as the preindex search scope — articles in these journals
# are searched by Title/Abstract before MeSH indexing (lowercase, full title)
priority_journals:
  - the new england journal of medicine
  - the lancet
  - the lancet. neurology
  - jama
  - jama neurology
  - stroke
  - annals of neurology
  - neurology
  - circulation
  - bmj (clinical research ed.)
  - annals of internal medicine
  - european stroke journal
  - international journal of stroke
```

```python
@dataclass
class RuleFilterConfig:
    include_article_types: list[str]
    exclude_article_types: list[str]
    exclude_mesh_terms: list[str]
    require_language: str
    require_abstract: bool

@dataclass
class LLMTriageConfig:
    model: str
    max_tokens: int
    score_threshold: float
    max_articles: int
    min_articles: int          # Minimum articles guarantee (0 = disabled, backfills from below-threshold)
    min_score_floor: float     # Score floor for backfill eligibility (default: 0.50)
    use_prompt_caching: bool
    triage_prompt_file: str
    seen_pmids_file: str       # Path to per-domain dedup history (default: "data/seen-pmids.json")

@dataclass
class FilterConfig:
    rule_filter: RuleFilterConfig
    llm_triage: LLMTriageConfig
    priority_journals: list[str]
```

## Domain Scoping

When `--domain` is specified, this config is loaded from `config/domains/{domain}/filter-config.yaml` instead of `config/filter-config.yaml`. The schema is identical in both layouts. Domain-scoped configs should set `llm_triage.seen_pmids_file` to a per-domain path (e.g., `data/domains/stroke/seen-pmids.json`) to keep dedup history isolated. See architecture decision A10.

## Constraints

- `score_threshold` must be between 0.0 and 1.0
- `max_articles` must be >= 1
- `min_articles` must be >= 0 (0 disables backfill guarantee)
- `min_score_floor` must be between 0.0 and 1.0, and should be < `score_threshold`
- `max_tokens` must be between 50 and 500
- `triage_prompt_file` must point to an existing file
- `require_language` uses ISO 639-2 three-letter codes (e.g., "eng", "fre", "chi")
- `include_article_types` and `exclude_article_types` use PubMed's publication type controlled vocabulary (lowercase)
- When an article has both an included and excluded type, the include takes precedence
- `priority_journals` entries must be non-empty strings matching PubMed's `[Journal]` field (accepts full title, abbreviation, or ISSN). When non-empty, the pipeline runs preindex Title/Abstract searches limited to these journals alongside the MeSH search. Preindex articles pass through rule and LLM triage identically to MeSH-indexed articles; the `preindex` flag is preserved for downstream labeling.

## Changelog

| Date | Version | Change | Affected Specs |
|------|---------|--------|----------------|
| 2026-03-23 | v0 | Initial draft from filter spike | — |
| 2026-03-24 | v0 | Added `seen_pmids_file` to `LLMTriageConfig` for per-domain dedup | llm-triage |
| 2026-04-01 | v0 | Added `min_articles` and `min_score_floor` to `LLMTriageConfig` for minimum article guarantee | llm-triage |
| 2026-04-02 | v0 | Clarify `priority_journals` as preindex search scope (passed to search stage by pipeline) | pubmed-query |
