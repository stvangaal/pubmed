# Literature Summary

## Status
draft

## Version
v0

## Description
The output of the summarization stage. One literature summary per filtered PubMed record, containing both a full LLM-generated clinical summary (hybrid format) and a 2-sentence short summary (teaser). The blog page uses the full summary for all articles. The email digest uses the full summary for high-scoring articles and the short summary (with a blog link) for the rest. Also includes a per-article feedback link.

## Schema

```python
@dataclass
class LiteratureSummary:
    pmid: str                    # Source article PMID
    title: str                   # Article title (from source PubmedRecord)
    journal: str                 # Journal title (from source PubmedRecord)
    pub_date: str                # Publication date (from source PubmedRecord, YYYY-MM-DD or YYYY-MM)
    subdomain: str               # Clinical subdomain tag, e.g. "Acute Treatment"
    citation: str                # Formatted markdown citation: "Title. *Journal*. [PMID](URL)"
    research_question: str       # One-sentence research question
    key_finding: str             # One-sentence key finding with clinical implication
    design: str                  # Study type, N, population
    primary_outcome: str         # Result with numbers
    limitations: str             # Most important methodological caveat
    triage_score: float          # LLM triage relevance score from filter stage (0.0-1.0)
    summary_short: str           # 2-sentence teaser: research question + key finding
    triage_rationale: str        # LLM triage explanation from filter stage
    feedback_url: str            # Google Form URL with pre-filled PMID
    raw_llm_response: str        # Full LLM output (for debugging/auditing)
```

## Constraints

- `pmid`, `title`, `journal`, `pub_date` must match the corresponding fields on the source `PubmedRecord`
- `subdomain` must be one of the values from `SummaryConfig.subdomain_options`
- `citation` must include a hyperlink to `https://pubmed.ncbi.nlm.nih.gov/{pmid}/`
- `feedback_url` must include the PMID as a pre-filled form parameter
- `research_question` and `key_finding` must each be a single sentence
- `summary_short` must be exactly 2 sentences: the research question and the key finding, suitable as a standalone teaser in the email digest
- `triage_score` and `triage_rationale` are carried forward from the `PubmedRecord@filtered` source — they reflect why the filter stage selected this article
- `raw_llm_response` preserves the unprocessed LLM output for quality auditing

## Changelog

| Date | Version | Change | Affected Specs |
|------|---------|--------|----------------|
| 2026-03-23 | v0 | Initial draft from architecture spike | — |
| 2026-03-23 | v0 | Added triage_score and triage_rationale fields from filter spike | llm-summarize |
| 2026-03-23 | v0 | Added title, journal, pub_date fields for plain-text rendering and sorting | llm-summarize, digest-build |
| 2026-03-23 | v0 | Added summary_short field (2-sentence teaser) for tiered email digest rendering | llm-summarize, digest-build, blog-publish |
