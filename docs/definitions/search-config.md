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
class SearchConfig:
    mesh_terms: list[str]        # MeSH Major Topic terms, e.g. ["stroke"]
    additional_terms: list[str]  # Free-text terms ANDed into the query, e.g. ["brain ischemia"]
    date_window_days: int        # How many days back to search from run date
    api_key: str | None          # NCBI API key (optional, raises rate limit from 3 to 10 req/sec)
    retmax: int                  # Maximum results to fetch per query (default 200)
    require_abstract: bool       # If true, exclude articles with no abstract (default true)
    rate_limit_delay: float      # Seconds between API calls (default 0.4)
    exclude_mesh_terms: list[str]      # MeSH terms to exclude via NOT clauses, e.g. ["animals", "mice"]
    exclude_article_types: list[str]   # Publication types to exclude via NOT clauses, e.g. ["case reports"]
    require_language: str | None       # ISO 639-2 language code filter, e.g. "eng" (default None)
```

## Domain Scoping

When `--domain` is specified, this config is loaded from `config/domains/{domain}/search-config.yaml` instead of `config/search-config.yaml`. The schema is identical in both layouts. See architecture decision A10.

## Constraints

- `mesh_terms` must have at least one entry
- `date_window_days` must be between 1 and 90
- `retmax` must be between 1 and 10000 (PubMed API limit)
- `rate_limit_delay` must be >= 0.35 (PubMed requires ≤3 req/sec without API key)
- If `api_key` is provided, `rate_limit_delay` can be reduced to >= 0.1 (10 req/sec)
- `exclude_mesh_terms` entries use PubMed MeSH vocabulary (case-insensitive)
- `exclude_article_types` entries use PubMed publication type controlled vocabulary (case-insensitive)
- `require_language` uses ISO 639-2 three-letter codes (e.g., "eng", "fre"); null means no language filter

## Changelog

| Date | Version | Change | Affected Specs |
|------|---------|--------|----------------|
| 2026-03-23 | v0 | Initial draft from search spike | — |
| 2026-03-31 | v0 | Added exclude_mesh_terms, exclude_article_types, require_language (moved from filter-config) | pubmed-query, rule-filter |
