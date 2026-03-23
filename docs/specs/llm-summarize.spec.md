---
name: llm-summarize
status: ready
owner: summarize
owns:
  - src/summarize/llm_summarize.py
  - src/summarize/parse_summary.py
  - tests/summarize/test_llm_summarize.py
  - tests/summarize/test_parse_summary.py
  - config/summary-config.yaml
  - config/prompts/summary-prompt.md
requires:
  - name: pubmed-record
    version: v0
  - name: summary-config
    version: v0
provides:
  - name: literature-summary
    version: v0
---

# LLM Summarize

## Status
ready

## Target Phase
Phase 2

## Purpose
Generate stroke-domain clinical summaries for filtered PubMed records using an LLM. Each filtered article is summarized in a hybrid format (subdomain tag, citation, research question, key finding, structured details with limitations) and paired with a per-article feedback link. This is the pipeline's core value — summary quality determines whether the digest is useful to clinicians.

## Requires (Inbound Contracts)

| Dependency | Source | Definition |
|------------|--------|------------|
| Filtered PubMed records | filter stage | `pubmed-record` v0 (`@filtered` status) |
| Summary configuration | user config | `summary-config` v0 |

## Provides (Outbound Contracts)

| Export | Type | Definition |
|--------|------|------------|
| Literature summaries | data | `literature-summary` v0 |

## Behaviour

### Input
A list of `PubmedRecord` objects with status `@filtered` (typically ~5 per run) and a `SummaryConfig`.

### Processing
For each filtered record:

1. **Format the prompt.** Insert the record's `title`, `journal`, `authors` (first 3 + "et al."), `pmid`, `article_types`, and `abstract` into the `SummaryConfig.prompt_template`.

2. **Call the LLM.** Send the formatted prompt to the model specified in `SummaryConfig.model` with `SummaryConfig.max_tokens`. Store the raw response.

3. **Parse the response.** Extract structured fields from the LLM output:
   - `subdomain` — validate against `SummaryConfig.subdomain_options`
   - `citation` — verify it contains the PMID link
   - `research_question` — text after "**Research Question:**"
   - `key_finding` — the paragraph between Research Question and Details
   - `design` — text after "- Design:"
   - `primary_outcome` — text after "- Primary outcome:"
   - `limitations` — text after "- Limitations:"

4. **Parse the short summary.** Extract `summary_short` — text after "**Short Summary:**". This is a 2-sentence teaser produced by the LLM in the same call as the full summary. It is used by the email digest for articles below the `full_summary_threshold`.

5. **Generate feedback URL.** Construct `{feedback_form_url}?{feedback_pmid_field}={pmid}` from the config and record.

6. **Carry forward source data.** Copy from the source `PubmedRecord` into the `LiteratureSummary`:
   - `title`, `journal`, `pub_date` — for plain-text rendering and sorting
   - `triage_score`, `triage_rationale` — for digest ordering and auditing

7. **Assemble the `LiteratureSummary`.** Populate all fields including `summary_short`. Retain `raw_llm_response` for auditing.

### Error handling
- If the LLM call fails, retry once. If it fails again, log the error and skip the article (do not block the rest of the digest).
- If parsing fails (e.g., LLM output doesn't match expected format), log a warning with the raw response and skip the article.
- If `subdomain` is not in the allowed list, default to the closest match or log and skip.

### Output
A list of `LiteratureSummary` objects, one per successfully summarized article.

## Decisions

| ID | Decision | Alternatives Considered | Rationale | Date |
|----|----------|------------------------|-----------|------|
| LS1 | One LLM call per article, not batch | Batch all articles in one prompt | Individual calls allow per-article error handling and retry. At ~5 articles/run, overhead is negligible. Batch prompts risk quality degradation with long context. | 2026-03-23 |
| LS2 | Parse structured fields from markdown output | Request JSON output from LLM | Markdown output is human-readable for debugging and auditing. JSON parsing adds fragility with no benefit at this volume. The hybrid format has clear delimiters. | 2026-03-23 |
| LS3 | Skip articles on parse failure rather than halt | Halt pipeline on any failure | A digest with 4 of 5 articles is better than no digest. Failures are logged for investigation. | 2026-03-23 |
| LS4 | Store raw LLM response alongside parsed fields | Discard raw response after parsing | Raw response enables quality auditing and prompt iteration without re-running the pipeline. Storage cost is trivial. | 2026-03-23 |
| LS5 | Generate summary_short in the same LLM call as the full summary | Separate LLM call; derive by concatenating parsed fields | Single call keeps cost flat. LLM-authored teaser reads more naturally than mechanical concatenation of research_question + key_finding. Cost is ~20 extra tokens/article. | 2026-03-23 |
| LS6 | Sonnet for summarization (same as triage), configurable via YAML | Opus for summarization; hardcoded model | Sonnet produces good structured summaries at ~5x lower cost than Opus. The rigid prompt format means the model follows instructions well. Both triage and summary models are already configurable in their respective YAML configs — upgrade to Opus with a one-line change if quality doesn't meet the bar. | 2026-03-23 |

## Tests

### Unit Tests

- **test_format_prompt**: Given a `PubmedRecord` and `SummaryConfig`, verify the prompt template is populated with correct values and all placeholders are replaced.
- **test_parse_summary_valid**: Given a well-formed LLM response in hybrid format, verify all `LiteratureSummary` fields are correctly extracted.
- **test_parse_summary_malformed**: Given an LLM response missing expected sections, verify a warning is logged and `None` is returned.
- **test_subdomain_validation**: Verify that an unrecognized subdomain tag is caught and handled (logged, article skipped or closest match used).
- **test_feedback_url_construction**: Verify the feedback URL is correctly constructed with pre-filled PMID from config values.
- **test_citation_format**: Verify the citation includes title, journal in italics, and a valid PubMed hyperlink.
- **test_summary_short_parsed**: Verify `summary_short` is extracted from the LLM response's "**Short Summary:**" section and contains exactly 2 sentences.

### Contract Tests

- **test_output_conforms_to_literature_summary**: Verify that the output of `summarize()` produces objects matching the `literature-summary` definition schema.
- **test_input_expects_filtered_pubmed_record**: Verify that the summarizer only accepts `PubmedRecord` objects with status `"filtered"` and rejects other statuses.
- **test_config_matches_summary_config_schema**: Verify that `config/summary-config.yaml` deserializes into a valid `SummaryConfig` object.

### Integration Tests

- **test_end_to_end_summarize**: Given a real (or realistic fixture) `PubmedRecord@filtered`, call the actual LLM API and verify the output parses into a valid `LiteratureSummary`. (Requires `ANTHROPIC_API_KEY`; skip in CI if not available.)
- **test_summarize_with_retry**: Simulate a transient LLM failure on first call, verify retry succeeds and produces valid output.

## Environment Requirements

- Requires `ANTHROPIC_API_KEY` environment variable for LLM calls
- Integration tests make real API calls; unit and contract tests are fully local
- Python 3.11+ with `anthropic` package

## Implementation Notes

- The prompt template validated in the spike is stored in `config/summary-config.yaml` as the default. Users can modify it without touching code.
- Use `anthropic.Anthropic()` client — it reads `ANTHROPIC_API_KEY` from the environment automatically.
- The parser should use simple string splitting on the markdown delimiters (`**Research Question:**`, `**Details:**`, `- Design:`, etc.) rather than regex. The format is predictable enough that string operations are clearer and easier to debug.
- Consider `asyncio` for parallel LLM calls if latency becomes an issue at higher volumes, but synchronous sequential calls are fine for v1 (~5 articles).
