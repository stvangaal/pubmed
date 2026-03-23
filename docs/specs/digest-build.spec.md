---
name: digest-build
status: ready
owner: distribute
owns:
  - src/distribute/digest_build.py
  - tests/distribute/test_digest_build.py
  - config/distribute-config.yaml
requires:
  - name: literature-summary
    version: v0
  - name: distribute-config
    version: v0
provides:
  - name: email-digest
    version: v0
---

# Digest Build

## Status
ready

## Target Phase
Phase 2

## Purpose
Assemble literature summaries into a formatted digest ready to paste into an email. Produces both markdown (for rich email clients) and plain-text (for simple pasting) versions. This is the pipeline's final output in v1 — automated sending is deferred.

## Requires (Inbound Contracts)

| Dependency | Source | Definition |
|------------|--------|------------|
| Literature summaries | summarize stage | `literature-summary` v0 |
| Distribution configuration | user config | `distribute-config` v0 |

## Provides (Outbound Contracts)

| Export | Type | Definition |
|--------|------|------------|
| Email digest (markdown) | file | `email-digest` v0 — written to `output.file` |
| Email digest (plain text) | file | written to `output.plain_text_file` when `output.plain_text` is true |

## Behaviour

### Input
A list of `LiteratureSummary` objects and a `DistributeConfig`.

### Assembly

The digest is assembled in three sections:

#### 1. Opening

Render the `opening` template from config, substituting:
- `{date_range}` — the search date window (e.g., "Mar 16 – Mar 22, 2026"), passed in from the pipeline run metadata
- `{article_count}` — number of summaries in this digest

#### 2. Content

Sort summaries according to `sort_by`:
- `triage_score` (default) — highest relevance first
- `subdomain` — grouped by subdomain (Acute Treatment, Prevention, Rehabilitation, etc.), then by score within each group
- `pub_date` — most recent first

For each summary, render in the hybrid format:

**Markdown version:**
```
**{subdomain}**
{citation}

**Research Question:** {research_question}

{key_finding}

**Details:**
- Design: {design}
- Primary outcome: {primary_outcome}
- Limitations: {limitations}

[Feedback on this article]({feedback_url})

---
```

**Plain-text version:**
```
[{subdomain}]
{title}. {journal}. PMID {pmid} (https://pubmed.ncbi.nlm.nih.gov/{pmid}/)

Research Question: {research_question}

{key_finding}

Details:
- Design: {design}
- Primary outcome: {primary_outcome}
- Limitations: {limitations}

Feedback: {feedback_url}

---
```

#### 3. Closing

Append the `closing` text from config.

### Feedback URLs

Each `LiteratureSummary` already has `feedback_url` populated (constructed by the summarize stage from `summary-config` settings). The digest-build spec uses it as-is — no feedback config needed in distribute-config.

### Output

Write two files:
1. **Markdown digest** — to `output.file` (default: `output/digest.md`)
2. **Plain-text digest** — to `output.plain_text_file` (default: `output/digest.txt`) when `output.plain_text` is true

Also print the plain-text version to stdout so the pipeline runner sees the result immediately.

### Empty Digest

If the summary list is empty (e.g., quiet week or all articles failed summarization):
- Write a short digest: opening + "No practice-relevant articles identified this week." + closing
- Log a notice, do not error

## Decisions

| ID | Decision | Alternatives Considered | Rationale | Date |
|----|----------|------------------------|-----------|------|
| DB1 | Generate paste-ready text, not send email | Automated SMTP; API-based email service | v1 sends to a comms person who forwards. Paste-ready text avoids email deliverability complexity. Upgrade path: add an `email-send` spec later. | 2026-03-23 |
| DB2 | Both markdown and plain-text output | Markdown only; HTML | Some email clients strip markdown. Plain text ensures the content is usable everywhere. HTML adds templating complexity with no value in v1. | 2026-03-23 |
| DB3 | Configurable sort order | Fixed by score; fixed by subdomain | Different audiences may prefer different ordering. Score-first is the sensible default (most important articles first), but subdomain grouping is useful for teams with subspecialty interests. | 2026-03-23 |
| DB4 | Print to stdout in addition to file | File only; clipboard | Stdout makes the digest visible in the GitHub Actions run log and in local terminal runs. Clipboard is platform-dependent. | 2026-03-23 |

## Tests

### Unit Tests

- **test_opening_template**: Given config with `{date_range}` and `{article_count}` placeholders, verify they are substituted correctly.
- **test_sort_by_score**: Given 3 summaries with different scores, verify output is ordered highest-first.
- **test_sort_by_subdomain**: Given summaries across subdomains, verify grouping and within-group score ordering.
- **test_markdown_format**: Given a single summary, verify the markdown output matches the expected template exactly.
- **test_plain_text_format**: Given a single summary, verify plain-text output has no markdown syntax and includes full PubMed URLs.
- **test_feedback_url_included**: Verify each article section includes the feedback URL.
- **test_empty_digest**: Given an empty summary list, verify the output includes the "no articles" message with opening and closing.
- **test_closing_appended**: Verify the closing text appears at the end of the digest.

### Contract Tests

- **test_input_accepts_literature_summary**: Verify the builder accepts objects conforming to `literature-summary` v0.
- **test_config_matches_distribute_config_schema**: Verify `config/distribute-config.yaml` deserializes into a valid `DistributeConfig`.

### Integration Tests

N/A — no external dependencies. Digest build is a pure function of its inputs (summaries + config).

## Implementation Notes

- The markdown and plain-text renderers should share the same ordering and content logic, differing only in formatting. Extract a common `render_summary(summary, format)` function.
- The `output/` directory should be gitignored — it contains ephemeral run output, not config.
- For local development, printing to stdout is sufficient. The file output matters for GitHub Actions runs where the artifact needs to be retrievable.
