---
name: search
owner: architecture
---

# Search

## Purpose

Query the PubMed E-utilities API for recent publications across the configured domain's search terms. Runs two parallel query strategies: MeSH-based search (for indexed articles, using `[Date - MeSH Date]`) and Title/Abstract text search limited to priority journals (for pre-MeSH articles, using `[Date - Entry]`). This is the pipeline's entry point — it produces the raw set of candidate records that all downstream stages operate on.

## Boundaries

**Input:** Schedule trigger (GitHub Actions cron, weekly)

**Output:** `pubmed-record@retrieved` — raw publication records with all fields needed by the filter stage (~40-130/run, mix of MeSH-indexed and preindex articles)

## Member Specs

| Spec | Responsibility |
|------|---------------|
| pubmed-query | Build and execute PubMed API queries from search config; parse response into pubmed-record objects |

## Internal Structure

Single spec — the search stage has one job. If search complexity grows (e.g., multiple query strategies, retry logic), additional specs would be added here.

## Boundary Definitions

| Definition | Access |
|------------|--------|
| `search-config` | reads — query terms, MeSH terms, date window, API key |
| `filter-config` | reads — `priority_journals` list (passed through pipeline for preindex search scope) |
| `pubmed-record` | writes — creates records with `@retrieved` status, tagged with `source_topic` and `preindex` |

## Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| S1 | Use PubMed E-utilities (esearch + efetch) rather than a third-party wrapper | Direct API access avoids dependencies, is well-documented, and gives full control over query construction. |
| S2 | Parallel preindex Title/Abstract search for priority journals | Catches practice-changing articles before MeSH indexing. Parallel execution within `multi_search()` avoids latency. Journal limitation keeps noise manageable. `preindex` flag enables downstream labeling/suppression. |
