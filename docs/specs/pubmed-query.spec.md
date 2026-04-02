---
name: pubmed-query
status: ready
owner: search
owns:
  - src/search/pubmed_query.py
  - src/search/date_normalize.py
  - tests/search/test_pubmed_query.py
  - tests/search/test_date_normalize.py
  - tests/search/test_multi_search.py
  - config/search-config.yaml
requires:
  - name: search-config
    version: v0
  - name: filter-config
    version: v0
    note: priority_journals list passed through pipeline for preindex search
provides:
  - name: pubmed-record
    version: v0
---

# PubMed Query

## Status
ready

## Target Phase
Phase 1

## Purpose
Query PubMed's E-utilities API for recent stroke-related publications and parse the results into `PubmedRecord` objects. This is the pipeline's entry point — it produces the raw candidate set that all downstream stages operate on.

## Requires (Inbound Contracts)

| Dependency | Source | Definition |
|------------|--------|------------|
| Search configuration | user config | `search-config` v0 |

## Provides (Outbound Contracts)

| Export | Type | Definition |
|--------|------|------------|
| Retrieved PubMed records | data | `pubmed-record` v0 (`@retrieved` status) |

## Behaviour

### Query Construction (MeSH Search)

Build the term part of a PubMed query string from `SearchConfig`:

1. Combine `mesh_terms` as OR-joined `"term"[MeSH Major Topic]` clauses.
2. AND with any `additional_terms` (free-text, OR-joined).

Date filtering is applied via the esearch API's `datetype`, `mindate`, `maxdate` parameters (not embedded in the query string):
- `datetype=mhda` — filter by MeSH indexing date (when NLM assigned MeSH terms). This ensures articles are found when they become MeSH-searchable, preventing permanent misses when indexing takes longer than `date_window_days`.
- `mindate` = run_date - date_window_days, `maxdate` = run_date - 1 day. PubMed date ranges are **inclusive on both ends**. The offset-by-one prevents the same article appearing in consecutive runs.

Example constructed query (term part only):
```
"stroke"[MeSH Major Topic]
```
With esearch params: `datetype=mhda&mindate=2026/03/16&maxdate=2026/03/22`

### Query Construction (Preindex Search)

For each topic, build a parallel Title/Abstract query limited to priority journals. This catches articles published in top-tier journals before NLM assigns MeSH terms:

1. Convert each `mesh_term` to `"term"[Title/Abstract]` (OR-joined). Include `additional_terms` if present.
2. AND with a journal filter: OR-joined `"journal"[Journal]` clauses from `priority_journals`.

Date filtering via esearch params: `datetype=edat` (entry date — when the article entered PubMed). This is correct for preindex because we want articles from the moment they appear, before MeSH indexing.

Example constructed query (term part only):
```
("atrial fibrillation"[Title/Abstract]) AND
  ("the new england journal of medicine"[Journal] OR "the lancet"[Journal])
```
With esearch params: `datetype=edat&mindate=2026/03/23&maxdate=2026/03/29`

### Search Flow Diagram

```
                          multi_search()
  ┌─────────────────────────────────────────────────────────────┐
  │                                                             │
  │   MeSH Searches (run first)                                 │
  │   ─────────────────────────                                 │
  │                                                             │
  │     "stroke"[MeSH Major Topic]                              │
  │       + esearch datetype=mhda                               │
  │         │                                                   │
  │         ├── primary search ──────────────────┐              │
  │         │                                    │              │
  │     "atrial fibrillation"[MeSH Major Topic]  │              │
  │       + esearch datetype=mhda                │              │
  │         │                                    │              │
  │         ├── topic: af ───────────────────┐   │              │
  │         ⋮  (one per topic)               │   │              │
  │                                          ▼   ▼              │
  │                                     ┌──────────┐           │
  │                                     │  Dedup   │           │
  │   Preindex Searches (run second)    │  by PMID │           │
  │   ──────────────────────────────    │  (first  │           │
  │                                     │   seen   │           │
  │     "stroke"[Title/Abstract]        │   wins)  │           │
  │       AND journals[Journal]         └────┬─────┘           │
  │       + esearch datetype=edat            │                  │
  │         │                                │                  │
  │         ├── primary (preindex) ──────────┤                  │
  │         │                                │                  │
  │     "atrial fibrillation"[Title/Abs.]    │                  │
  │       AND journals[Journal]              │                  │
  │       + esearch datetype=edat            │                  │
  │         │                                │                  │
  │         ├── topic: af (preindex) ────────┤                  │
  │         ⋮                                │                  │
  │                                          ▼                  │
  │                                   PubmedRecord[]            │
  │                                   (preindex=False           │
  │                                    for MeSH hits,           │
  │                                    preindex=True            │
  │                                    for preindex-only)       │
  │                                          │                  │
  └──────────────────────────────────────────┼──────────────────┘
                                             │
                                             ▼
                                     ┌──────────────┐
                                     │ rule_filter() │
                                     │ llm_triage()  │──▶ seen_pmids.json
                                     └──────┬───────┘    (persistent,
                                            │             cross-run dedup)
                                            ▼
                                     PubmedRecord@filtered
```

**Date field summary** (applied via esearch API params, not inline query syntax):
- MeSH search: `datetype=mhda` — finds articles when MeSH terms are assigned
- Preindex search: `datetype=edat` — finds articles when they first enter PubMed
- Suppression: `seen_pmids.json` prevents an article from being triaged twice across runs (preindex week 1 → MeSH week 2)

### API Calls

Two sequential E-utilities calls:

1. **esearch** — send the query, get back a list of PMIDs and total count.
   - Use `retmax` from config (default 200).
   - Parse the JSON response to extract `idlist` and `count`.

2. **efetch** — send the PMID list, get back full XML records.
   - Fetch in batches of 200 if total exceeds `retmax`.
   - Parse the XML response into individual `PubmedArticle` elements.

Rate limiting: sleep `rate_limit_delay` seconds between every HTTP request to respect PubMed's rate limits.

### XML Parsing

For each `PubmedArticle` element, extract fields into a `PubmedRecord`:

| Field | XML Path | Notes |
|-------|----------|-------|
| `pmid` | `.//PMID` | Text content |
| `title` | `.//ArticleTitle` | Use `itertext()` to capture mixed content |
| `authors` | `.//Author` | `LastName` + first char of `ForeName` |
| `journal` | `.//Journal/Title` | Text content |
| `abstract` | `.//AbstractText` | Join all parts with spaces; `itertext()` for mixed content |
| `pub_date` | `.//ArticleDate` or `.//PubDate` | See date normalization below |
| `article_types` | `.//PublicationType` | All text values |
| `mesh_terms` | `.//MeshHeading/DescriptorName` | All text values |
| `language` | `.//Language` | Text content |
| `doi` | `.//ArticleId[@IdType="doi"]` | Text content, `None` if absent |

Set `status = "retrieved"`, `triage_score = None`, `triage_rationale = None`.

### Date Normalization

PubMed returns dates in multiple formats. Normalize to `YYYY-MM-DD` or `YYYY-MM`:

1. Try `ArticleDate` first (electronic publication) — has `Year`, `Month`, `Day` sub-elements. Format as `YYYY-MM-DD`.
2. Fall back to `PubDate` — has `Year` and optionally `Month` (may be name like "Mar" or number like "03") and `Day`.
3. Fall back to `MedlineDate` — free-text like "2026 Mar-Apr". Extract year and first month.

Month name conversion: `Jan`→`01`, `Feb`→`02`, ..., `Dec`→`12`.

### Exclusions

Exclude articles at parse time (do not include in output):
- Missing or empty abstract (when `require_abstract` is true)
- Missing PMID

Log excluded articles with reason.

### Multi-Search (Topic Expansion)

When `search_profiles` are configured, `multi_search()` runs the primary search plus one independent search per profile, then deduplicates by PMID:

1. Run the primary `search()` with the top-level `mesh_terms`.
2. For each `SearchProfile`, build a `SearchConfig` using the profile's `mesh_terms`/`additional_terms` and the parent config's `date_window_days`, `retmax`, `require_abstract`, `rate_limit_delay`, and `api_key`.
3. Run `search()` for each profile config.
4. Merge results: deduplicate by PMID (first-seen wins).
5. Return the merged list and the sum of all esearch counts.

When `search_profiles` is empty (the default), `multi_search()` behaves identically to `search()`.

### Preindex Searches (within multi_search)

When `preindex_journals` is provided (from `FilterConfig.priority_journals` via the pipeline), `multi_search()` runs additional Title/Abstract queries after all MeSH searches complete:

1. For each topic (and primary), build a preindex query via `build_preindex_query()`.
2. Execute via the shared `_execute_query()` helper (same esearch → efetch → parse flow).
3. Deduplicate against the same PMID set — MeSH hits ran first, so they win.
4. Tag preindex-only hits with `preindex=True` and the appropriate `source_topic`.

When `preindex_journals` is `None` or empty, no preindex searches run.

### Output

Return a list of `PubmedRecord` objects with status `"retrieved"` and the total count from esearch (for logging/metrics). Each record is tagged with `source_topic` (topic name or `"primary"`) and `preindex` (`True` for articles found only via text search, `False` for MeSH-indexed hits).

## Decisions

| ID | Decision | Alternatives Considered | Rationale | Date |
|----|----------|------------------------|-----------|------|
| PQ1 | MeSH search uses `datetype=mhda`; preindex search uses `datetype=edat` (via esearch API params) | Inline `[Date - Entry]` in query string (original); `[Date - Publication]`; single date field for both | MeSH search needs MHDA (when MeSH terms were assigned) to avoid permanently missing articles that take >7 days to index. Preindex search needs EDAT (entry date) to catch articles the moment they appear. Date filtering via esearch API params (`datetype`/`mindate`/`maxdate`) rather than inline query syntax — PubMed does not support `[Date - MeSH Date]` as an inline field tag. | 2026-04-02 |
| PQ2 | Use E-utilities directly, not a wrapper library | BioPython Entrez, PyMed | Direct API access avoids dependencies, is well-documented, and gives full control. The API surface we need is small (esearch + efetch). | 2026-03-23 |
| PQ3 | Broad MeSH query, let filter stage narrow | Narrow query with article type filters | The spike showed filtered_types returned only 4/week — too few for robust filtering. Broad query (~42/week) gives the filter stage enough candidates to work with. | 2026-03-23 |
| PQ4 | Rate limit with configurable delay, not hardcoded | Hardcoded 0.4s; no delay | Configurable respects both API-key and no-key scenarios. Default 0.4s is safe for keyless access (< 3 req/sec). | 2026-03-23 |
| PQ5 | Multiple independent queries for topic expansion, dedup by PMID | Single OR-joined query (reverted); widen primary mesh_terms; PubMed elink API | Independent queries avoid NOT-clause syntax issues that caused the previous revert. Each profile is isolated — failures or volume spikes are contained. Dedup is trivial (PMID set). Filter stage unchanged per PQ3. | 2026-04-01 |
| PQ6 | Parallel preindex Title/Abstract search limited to priority journals | Wider MeSH query; separate pipeline stage; OR text terms into MeSH query | Top-tier journals appear in PubMed before MeSH indexing (days to weeks). A parallel text search catches these early without polluting the precise MeSH query. Journal limitation keeps noise manageable. MeSH dedup ensures one record per article. `preindex` flag enables downstream labeling. | 2026-04-02 |

## Tests

### Unit Tests

- **test_build_query**: Given a `SearchConfig` with specific MeSH terms and date window, verify the constructed query string matches expected PubMed syntax.
- **test_parse_record_complete**: Given a sample PubMed XML element with all fields populated, verify all `PubmedRecord` fields are correctly extracted.
- **test_parse_record_missing_abstract**: Verify the article is excluded and a log message is produced.
- **test_parse_record_missing_doi**: Verify `doi` is `None` and no warning is raised (DOI is optional).
- **test_date_normalize_full**: Given `Year=2026, Month=03, Day=15`, verify output is `"2026-03-15"`.
- **test_date_normalize_month_name**: Given `Year=2026, Month=Mar`, verify output is `"2026-03"`.
- **test_date_normalize_medline**: Given `MedlineDate="2026 Mar-Apr"`, verify output is `"2026-03"`.
- **test_author_format**: Given `LastName=Smith, ForeName=John Alexander`, verify output is `"Smith J"`.
- **test_author_no_forename**: Given `LastName=Smith` only, verify output is `"Smith"`.

- **test_multi_search_no_profiles**: Verify `multi_search()` with no profiles behaves identically to `search()`.
- **test_multi_search_merges_results**: Verify results from primary + profiles are merged.
- **test_multi_search_deduplicates_by_pmid**: Verify duplicate PMIDs across queries are kept once (first-seen wins).
- **test_multi_search_profile_inherits_config**: Verify profile queries inherit parent config fields.

- **test_build_preindex_query_uses_title_abstract**: Verify `build_preindex_query()` uses `[Title/Abstract]`, not `[MeSH Major Topic]`.
- **test_build_preindex_query_includes_journal_filter**: Verify journal names appear as `[Journal]` clauses.
- **test_build_preindex_query_uses_date_entry**: Verify preindex query uses `[Date - Entry]`.
- **test_preindex_records_tagged**: Verify preindex-only hits have `preindex=True` and correct `source_topic`.
- **test_mesh_hit_wins_dedup_over_preindex**: Verify same PMID from MeSH and preindex keeps `preindex=False`.
- **test_preindex_runs_for_topics**: Verify preindex searches run for each topic, not just primary.
- **test_no_preindex_when_journals_empty**: Verify no preindex searches when `preindex_journals` is `None`.
- **test_preindex_dedup_across_topics**: Verify preindex hit already found by topic MeSH is deduplicated.

### Contract Tests

- **test_output_conforms_to_pubmed_record**: Verify that parsed output matches the `pubmed-record` definition schema, including status `"retrieved"` and null triage fields.
- **test_config_matches_search_config_schema**: Verify that `config/search-config.yaml` deserializes into a valid `SearchConfig`.

### Integration Tests

- **test_esearch_live**: Call the real PubMed API with a known query and verify PMIDs are returned. (Requires network; skip in CI if offline.)
- **test_efetch_live**: Fetch a known PMID and verify the XML contains expected elements.
- **test_end_to_end_search**: Run the full search pipeline with a small `retmax` and verify output is a list of valid `PubmedRecord` objects.

## Environment Requirements

- Requires network access to `eutils.ncbi.nlm.nih.gov`
- Optional `NCBI_API_KEY` environment variable for higher rate limits
- Integration tests make real API calls; unit and contract tests are fully local
- Python 3.11+, no external packages required (uses `urllib` and `xml.etree`)

## Implementation Notes

- Use `urllib.request` and `xml.etree.ElementTree` from the standard library — no external HTTP or XML dependencies needed.
- The spike code in `spikes/search/spike_search.py` has a working parser that covers all field extraction and date normalization. Extract and refine it.
- For the default `config/search-config.yaml`, use the broad query that returned ~42 results/week in the spike: `mesh_terms: ["stroke"]`, `date_window_days: 7`, `retmax: 200`.
- `_execute_query()` is a shared helper that handles the esearch → efetch → parse pipeline for a pre-built query string. Both `search()` (MeSH) and the preindex loop in `multi_search()` use it, avoiding code duplication.
- `build_preindex_query()` mirrors `build_query()` but substitutes `[Title/Abstract]` for `[MeSH Major Topic]`, adds a journal filter clause, and uses `[Date - Entry]` instead of `[Date - MeSH Date]`.
