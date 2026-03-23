---
name: search
owner: architecture
---

# Search

## Purpose

Query the PubMed E-utilities API for stroke-related publications indexed within the configured date window. This is the pipeline's entry point — it produces the raw set of candidate records that all downstream stages operate on.

## Boundaries

**Input:** Schedule trigger (GitHub Actions cron, weekly)

**Output:** `pubmed-record@retrieved` — raw publication records with all fields needed by the filter stage (~200/run)

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
| `pubmed-record` | writes — creates records with `@retrieved` status |

## Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| S1 | Use PubMed E-utilities (esearch + efetch) rather than a third-party wrapper | Direct API access avoids dependencies, is well-documented, and gives full control over query construction. |
