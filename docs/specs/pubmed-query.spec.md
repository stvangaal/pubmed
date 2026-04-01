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

### Query Construction

Build a PubMed query string from `SearchConfig`:

1. Combine `mesh_terms` as OR-joined `"term"[MeSH Major Topic]` clauses.
2. AND with any `additional_terms` (free-text, OR-joined).
3. AND with a date range filter: `{run_date - date_window_days}:{run_date - 1 day}[Date - Entry]`.
   - Use `[Date - Entry]` (when PubMed indexed it), not `[Date - Publication]` — this catches articles published earlier but newly indexed.
   - PubMed date ranges are **inclusive on both ends**. To prevent overlap between consecutive weekly runs, the end date must be offset by one day (e.g., for a run on March 23, the range is `2026/03/16:2026/03/22`). The next run starts on `2026/03/23`.

Example constructed query:
```
"stroke"[MeSH Major Topic] AND 2026/03/16:2026/03/22[Date - Entry]
```

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

### Output

Return a list of `PubmedRecord` objects with status `"retrieved"` and the total count from esearch (for logging/metrics).

## Decisions

| ID | Decision | Alternatives Considered | Rationale | Date |
|----|----------|------------------------|-----------|------|
| PQ1 | Use `[Date - Entry]` not `[Date - Publication]` | `[Date - Publication]`, `[Date - Create]` | Entry date captures when PubMed indexed the article, which is what matters for a "new this week" pipeline. Publication date may be weeks or months earlier. | 2026-03-23 |
| PQ2 | Use E-utilities directly, not a wrapper library | BioPython Entrez, PyMed | Direct API access avoids dependencies, is well-documented, and gives full control. The API surface we need is small (esearch + efetch). | 2026-03-23 |
| PQ3 | Broad MeSH query, let filter stage narrow | Narrow query with article type filters | The spike showed filtered_types returned only 4/week — too few for robust filtering. Broad query (~42/week) gives the filter stage enough candidates to work with. | 2026-03-23 |
| PQ4 | Rate limit with configurable delay, not hardcoded | Hardcoded 0.4s; no delay | Configurable respects both API-key and no-key scenarios. Default 0.4s is safe for keyless access (< 3 req/sec). | 2026-03-23 |
| PQ5 | Multiple independent queries for topic expansion, dedup by PMID | Single OR-joined query (reverted); widen primary mesh_terms; PubMed elink API | Independent queries avoid NOT-clause syntax issues that caused the previous revert. Each profile is isolated — failures or volume spikes are contained. Dedup is trivial (PMID set). Filter stage unchanged per PQ3. | 2026-04-01 |

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
