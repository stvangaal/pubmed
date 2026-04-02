# Search Config

## Status
draft

## Version
v0

## Description
User-facing configuration for the search stage. Controls the PubMed query construction, date window, and API settings. Users edit this as a YAML file without touching source code.

## Schema

```python
@dataclass
class SearchProfile:
    name: str                    # Human-readable label, e.g. "atrial-fibrillation"
    mesh_terms: list[str]        # MeSH Major Topic terms for this profile
    additional_terms: list[str]  # Free-text terms (optional, default [])

@dataclass
class SearchConfig:
    mesh_terms: list[str]        # MeSH Major Topic terms, e.g. ["stroke"]
    additional_terms: list[str]  # Free-text terms ANDed into the query, e.g. ["brain ischemia"]
    date_window_days: int        # How many days back to search from run date
    api_key: str | None          # NCBI API key (optional, raises rate limit from 3 to 10 req/sec)
    retmax: int                  # Maximum results to fetch per query (default 200)
    require_abstract: bool       # If true, exclude articles with no abstract (default true)
    rate_limit_delay: float      # Seconds between API calls (default 0.4)
    search_profiles: list[SearchProfile]  # Additional independent queries (optional, default [])
```

## Preindex Search

When `priority_journals` is configured in `filter-config.yaml`, the pipeline passes the journal list to `multi_search()` as the `preindex_journals` parameter. For each topic (and primary search), an additional Title/Abstract query runs in parallel, limited to the specified journals:

```
"term"[Title/Abstract] AND ("journal1"[Journal] OR "journal2"[Journal] OR ...) AND date_range[Date - Entry]
```

This catches articles published in top-tier journals before NLM assigns MeSH terms. The preindex search uses `[Date - Entry]` (PubMed entry date) while the MeSH search uses `[Date - MeSH Date]` (MeSH indexing date). MeSH hits take dedup priority; preindex-only hits are tagged with `preindex=True` on the `PubmedRecord`.

The journal list is not part of `SearchConfig` — it is passed through from `FilterConfig.priority_journals` by the pipeline orchestrator.

## Domain Scoping

When `--domain` is specified, this config is loaded from `config/domains/{domain}/search-config.yaml` instead of `config/search-config.yaml`. The schema is identical in both layouts. See architecture decision A10.

## Constraints

- `mesh_terms` must have at least one entry
- `date_window_days` must be between 1 and 90
- `retmax` must be between 1 and 10000 (PubMed API limit)
- `rate_limit_delay` must be >= 0.35 (PubMed requires ≤3 req/sec without API key)
- If `api_key` is provided, `rate_limit_delay` can be reduced to >= 0.1 (10 req/sec)
- Each `SearchProfile.mesh_terms` must have at least one entry
- Each `SearchProfile.name` must be non-empty

## Changelog

| Date | Version | Change | Affected Specs |
|------|---------|--------|----------------|
| 2026-03-23 | v0 | Initial draft from search spike | — |
| 2026-04-01 | v0 | Add optional search_profiles for topic expansion | pubmed-query |
| 2026-04-02 | v0 | Document preindex search behavior (journal list sourced from filter-config) | pubmed-query |
