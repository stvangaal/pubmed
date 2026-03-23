# PubMed Record

## Status
draft

## Version
v0

## Description
The core domain object flowing through the pipeline. Represents a single publication retrieved from PubMed's E-utilities API. Gains status qualifiers as it progresses through stages: `@retrieved` (raw from API), `@filtered` (passed rule-based and LLM triage).

## Schema

```python
@dataclass
class PubmedRecord:
    pmid: str                    # PubMed unique identifier
    title: str                   # Article title
    authors: list[str]           # Author names, e.g. ["Smith J", "Jones A"]
    journal: str                 # Journal title
    abstract: str                # Full abstract text
    pub_date: str                # Publication date, normalized to YYYY-MM-DD where possible, YYYY-MM as fallback
    article_types: list[str]     # PubMed publication types, e.g. ["Randomized Controlled Trial", "Meta-Analysis"]
    mesh_terms: list[str]        # MeSH terms assigned to this article
    language: str                # Language code, e.g. "eng"
    doi: str | None              # DOI if available
    status: str                  # Pipeline status: "retrieved" | "filtered"
    triage_score: float | None   # LLM triage relevance score (set by filter stage, None while @retrieved)
    triage_rationale: str | None # LLM triage explanation (set by filter stage, None while @retrieved)
```

## Constraints

- `pmid` must be a non-empty string of digits
- `abstract` must be non-empty (articles without abstracts are excluded at search stage)
- `status` must be one of: `"retrieved"`, `"filtered"`. Note: documentation uses `@retrieved` and `@filtered` as shorthand qualifiers (e.g., `PubmedRecord@filtered`), but the literal field value is the string without the `@` prefix.
- `triage_score` is `None` when status is `"retrieved"`; a float 0.0-1.0 when status is `"filtered"`
- `authors` uses "LastName FirstInitial" format, truncated to first 3 + "et al." for display
- `pub_date` is normalized by the search stage from PubMed's variable formats (e.g. "2026-Mar", "2026-02-12", "2026 Mar-Apr") to `YYYY-MM-DD` when day is available, `YYYY-MM` otherwise. Month names are converted to numbers.
- `article_types` uses PubMed's controlled vocabulary for publication types

## Changelog

| Date | Version | Change | Affected Specs |
|------|---------|--------|----------------|
| 2026-03-23 | v0 | Initial draft from architecture spike | — |
| 2026-03-23 | v0 | Added date normalization constraint from search spike | pubmed-query |
