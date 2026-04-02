---
name: llm-triage
status: ready
owner: filter
owns:
  - src/filter/llm_triage.py
  - tests/filter/test_llm_triage.py
  - config/prompts/triage-prompt.md
requires:
  - name: pubmed-record
    version: v0
  - name: filter-config
    version: v0
provides:
  - name: pubmed-record
    version: v0
---

# LLM Triage

## Status
ready

## Target Phase
Phase 1

## Purpose
Score rule-filtered PubMed records for clinical relevance using an LLM. This is the second pass of the hybrid filter — it applies clinical judgment to the ~30-80 articles that survive rule-based filtering, selecting the most practice-relevant ones for summarization. The triage score and rationale are carried forward to the summarization stage.

## Requires (Inbound Contracts)

| Dependency | Source | Definition |
|------------|--------|------------|
| Rule-filtered PubMed records | rule-filter spec | `pubmed-record` v0 (`@retrieved` status, post-rule-filter) |
| Filter configuration | user config | `filter-config` v0 (`llm_triage` section + `priority_journals`) |

## Provides (Outbound Contracts)

| Export | Type | Definition |
|--------|------|------------|
| Triage-scored records (above threshold) | data | `pubmed-record` v0 (`@filtered` status, triage fields populated) |
| Triage-scored records (below threshold) | data | `pubmed-record` v0 (`@filtered` status) — written to exclusion log |

## Behaviour

### Input
A list of `PubmedRecord` objects (post-rule-filter, status `@retrieved`) and an `LLMTriageConfig`. The input may include preindex articles (with `preindex=True`) that lack MeSH terms and specific article types. LLM triage scores these identically based on title, abstract, and journal. The `preindex` and `source_topic` fields are preserved through triage. Cross-run dedup via `seen_pmids.json` prevents articles found by preindex search in one run from being re-triaged when the MeSH search finds them in a later run.

### Prompt Structure

The triage prompt is split into two parts:

1. **System prompt** — loaded from `triage_prompt_file` (default: `config/prompts/triage-prompt.md`). Contains scoring guide, factors, domain-specific instructions, and scoring examples. This is the cacheable portion — identical across all articles in a run.

2. **User message** — per-article content assembled from the record:
   ```
   Title: {title}
   Journal: {journal}
   Type: {article_types}
   MeSH: {mesh_terms}
   Abstract: {abstract}  (truncated to 2000 chars)
   ```

The system prompt is stored as a separate file (not embedded in code) so users can tune scoring behavior without modifying source code.

### Processing

For each rule-filtered record:

1. **Assemble the user message** from the record's fields.
2. **Call the LLM** with the system prompt (cached) and user message.
3. **Parse the JSON response** — extract `score` (float, two decimal places) and `rationale` (string).
4. **Set triage fields** — populate `triage_score` and `triage_rationale` on the record. Set `status = "filtered"`.

### Prompt Caching

When `use_prompt_caching` is true, the system prompt is sent with `cache_control: {"type": "ephemeral"}`. This caches the system prompt after the first call, reducing input token costs by ~90% for subsequent calls in the same run.

Sonnet 4.6 requires a minimum of 2,048 tokens for caching. The triage prompt should include enough scoring examples and domain context to meet this threshold. If below threshold, caching silently degrades to uncached — no error.

### Scoring

The LLM returns a JSON object: `{"score": <float>, "rationale": "<string>"}`.

Score ranges (from the triage prompt):
- **0.90-1.00** — Practice-changing (new RCT results, updated guidelines, definitive meta-analyses)
- **0.80-0.89** — Highly relevant (strong evidence, authoritative clinical reviews from top journals, stroke imaging with diagnostic/prognostic impact)
- **0.70-0.79** — Clinically informative (solid evidence a clinician should know)
- **0.50-0.69** — Incremental (useful but not urgent)
- **0.00-0.49** — Low relevance or not relevant

### Domain-Specific Scoring Adjustments

The triage prompt includes guidance for stroke-specific scoring:
- **Authoritative clinical reviews** from top-tier journals (Lancet, NEJM, JAMA, etc.) are scored 0.80+ even without novel primary data — they are high-value for a clinical digest audience.
- **Stroke imaging studies** with diagnostic or prognostic implications for acute stroke workflows are scored 0.70+ — imaging findings directly influence clinical decisions in time-sensitive settings.
- **Trial protocols** without results are capped at 0.50-0.65 — informative but not actionable.

### Threshold and Cap

- Articles scoring >= `score_threshold` (default 0.70) are included.
- If more than `max_articles` (default 10) score above threshold, take the top `max_articles` by score.
- All scored articles (above and below threshold) are written to the output for auditing.

### Output

Three outputs:

1. **Included list** — `PubmedRecord` objects with status `@filtered`, `triage_score >= threshold`, sorted by score descending, capped at `max_articles`. These are passed to the summarization stage.

2. **Below-threshold list** — `PubmedRecord` objects with status `@filtered`, `triage_score < threshold`. Written to `filter-triage-below-threshold.json` with PMID, title, journal, score, and rationale.

3. **Combined exclusion log** — merged with the rule-filter exclusion log into `filter-exclusions.json`. Each entry includes:
   - `pmid`, `title`, `journal`
   - `excluded_by`: `"rule_filter"` or `"llm_triage"`
   - `reason` (for rule filter) or `score` + `rationale` (for LLM triage)

### Error Handling

- If JSON parsing fails, log warning with raw LLM response, assign score 0.0, continue.
- If LLM call fails, retry once. If retry fails, log error, assign score 0.0, continue.
- A run that scores zero articles above threshold still produces the exclusion log.

### Deduplication

Track previously seen PMIDs across pipeline runs using a simple JSON file (`data/seen-pmids.json`). Articles already seen in prior runs are excluded before LLM triage to avoid:
- Wasting tokens on articles already scored
- Duplicate articles appearing in consecutive digests

The seen-PMIDs list is updated after each successful run.

## Decisions

| ID | Decision | Alternatives Considered | Rationale | Date |
|----|----------|------------------------|-----------|------|
| LT1 | Score threshold (>= 0.70) instead of fixed top-N | Top 5; top 10; percentile-based | Fixed top-N creates arbitrary cutoffs within quality tiers. Threshold allows busy weeks to include more and quiet weeks to include fewer. Spike data showed 0.70 produces clean breaks. | 2026-03-23 |
| LT2 | Two decimal place scoring | One decimal (0.1 increments); integer 1-100 | Spike v1 showed 0.1 increments create too many ties (gap = 0.00 in 5/6 weeks). Two decimals differentiate within tiers while remaining human-readable. | 2026-03-23 |
| LT3 | Triage prompt stored as external file, not in code | Embedded in source; environment variable | The prompt IS the product for this stage. Users should be able to tune it without modifying source. External file also enables versioning and A/B testing. | 2026-03-23 |
| LT4 | Sonnet 4.6 for triage | Opus; Haiku; Sonnet 4.5 | Best cost/quality tradeoff for a scoring task. Sonnet 4.6 is the latest, handles two-decimal scoring well, and supports prompt caching at 2,048 tokens. | 2026-03-23 |
| LT5 | Carry triage score + rationale to summarization stage | Discard after filtering | Triage rationale provides context for the summarizer and is useful for digest readers and auditing. Storage cost is trivial. | 2026-03-23 |
| LT6 | Persist full exclusion log (rule filter + triage) | Log only above-threshold; discard | Full log enables troubleshooting false negatives. The AF guideline miss in spike v1 was caught by reviewing exclusion data. | 2026-03-23 |
| LT7 | Dedup via seen-PMIDs file across runs | Database; no dedup | PubMed date ranges are inclusive, causing 10+ duplicates per week at boundaries. Simple JSON file avoids infrastructure. Cleared periodically (e.g., quarterly). | 2026-03-23 |

## Tests

### Unit Tests

- **test_parse_valid_json_response**: Given a well-formed LLM response, verify score and rationale are extracted.
- **test_parse_malformed_response**: Given invalid JSON, verify score defaults to 0.0 and warning is logged.
- **test_threshold_filter**: Given scored articles, verify only those >= threshold appear in included list.
- **test_max_articles_cap**: Given 15 articles above threshold, verify only top 10 (by score) are included.
- **test_exclusion_log_format**: Verify log entries include PMID, title, journal, excluded_by, and score/rationale.
- **test_dedup_skips_seen_pmids**: Given a seen-PMIDs list, verify previously seen articles are not sent to LLM.
- **test_dedup_updates_after_run**: Verify seen-PMIDs file is updated with newly scored PMIDs after a run.
- **test_sort_order**: Verify output is sorted by triage_score descending.

### Contract Tests

- **test_output_conforms_to_pubmed_record_filtered**: Verify output records have status `"filtered"`, `triage_score` is a float 0.0-1.0, and `triage_rationale` is a non-empty string.
- **test_config_matches_filter_config_schema**: Verify `config/filter-config.yaml` `llm_triage` section deserializes correctly.

### Integration Tests

- **test_end_to_end_triage**: Given 5 real PubmedRecord objects, call the LLM and verify output parses correctly. (Requires `ANTHROPIC_API_KEY`; skip in CI if unavailable.)
- **test_prompt_caching_active**: Run 3 consecutive calls and verify `cache_read_input_tokens > 0` on the 2nd and 3rd calls.

## Environment Requirements

- Requires `ANTHROPIC_API_KEY` environment variable
- Integration tests make real API calls; unit and contract tests are fully local
- Python 3.11+ with `anthropic` package

## Implementation Notes

- The triage prompt validated in the spike is saved to `config/prompts/triage-prompt.md`. This is the file users edit to tune scoring.
- Use `anthropic.Anthropic()` client with system message as a cached content block.
- The exclusion log should merge with the rule-filter exclusion log into a single `filter-exclusions.json` per run. Append triage results to the same file.
- The `seen-pmids.json` dedup file lives in `data/` and is gitignored (it's per-installation state, not config).
