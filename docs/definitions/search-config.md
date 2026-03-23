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
    require_abstract: bool          # If true, exclude articles with no abstract (default true)
    rate_limit_delay: float      # Seconds between API calls (default 0.4)
```

## Constraints

- `mesh_terms` must have at least one entry
- `date_window_days` must be between 1 and 90
- `retmax` must be between 1 and 10000 (PubMed API limit)
- `rate_limit_delay` must be >= 0.35 (PubMed requires ≤3 req/sec without API key)
- If `api_key` is provided, `rate_limit_delay` can be reduced to >= 0.1 (10 req/sec)

## Changelog

| Date | Version | Change | Affected Specs |
|------|---------|--------|----------------|
| 2026-03-23 | v0 | Initial draft from search spike | — |
