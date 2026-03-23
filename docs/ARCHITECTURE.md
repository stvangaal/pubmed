# PubMed Stroke Monitor — Architecture

## Architecture Owner

The project maintainer (currently @stvangaal). Final authority over shared definitions, pipeline stage boundaries, and configuration surface design.

## Overview

A weekly automated pipeline that identifies practice-changing stroke publications from PubMed, summarizes them using an LLM, and delivers a curated digest for distribution to clinical audiences.

**Users:** Stroke clinicians and researchers who receive the weekly digest. Maintainers (1-2) who configure the pipeline. The comms person who forwards the digest to recipients.

**External dependencies:** PubMed E-utilities API (search and fetch), an LLM API (filtering triage and summarization), GitHub Pages (blog archive), an SMTP/email service (digest delivery, future), Google Forms (per-article feedback capture).

**Autonomy:** Runs weekly via GitHub Actions on a cron schedule. No human intervention required for normal operation.

**Distribution model:** Public GitHub repo. Users fork and configure via YAML files without modifying source code.

## Pipeline Diagram

```
  GitHub Actions cron                         GitHub Pages
  (Monday 8am UTC)                            (auto-deploy)
         │                                         ▲
         ▼                                         │
    PubmedRecord             PubmedRecord            LiteratureSummary
     @retrieved               @filtered                @summarized
         │                       │                         │
         ▼                       ▼                         ▼
┌─────────────────┐    ┌──────────────────┐    ┌────────────────────┐
│ SEARCH          │───▶│ FILTER           │───▶│ SUMMARIZE          │──┐
│                 │    │                  │    │                    │  │
│ • pubmed-query  │    │ • rule-filter    │    │ • llm-summarize   │  │
│                 │    │ • llm-triage     │    │                    │  │
└─────────────────┘    └──────────────────┘    └────────────────────┘  │
         ▲                      ▲                        ▲             │
    ┌────┴─────┐          ┌─────┴──────┐          ┌──────┴──────┐     │
    │ search   │          │ filter     │          │ summary    │     │
    │ config   │          │ config     │          │ config     │     │
    └──────────┘          └────────────┘          └────────────┘     │
      CONFIG                CONFIG                  CONFIG           │
                                                                     │
    ┌────────────────────────────────────────────────────────────────┘
    │
    │   BlogPage                 EmailDigest
    │    @published               @assembled
    │       │                        │
    ▼       ▼                        ▼
┌─────────────────────────────────────────────────────────────┐
│ DISTRIBUTE                                                  │
│                                                             │
│ • blog-publish ───▶ • digest-build ───▶ • email-send        │
│   (push to    blog    (tiered email      (deliver via       │
│    gh-pages)  URLs     rendering)         Resend API)       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
         ▲                    ▲                   ▲
    ┌────┴──────┐       ┌─────┴──────┐      ┌────┴─────┐
    │ blog      │       │ distribute │      │ email    │
    │ config    │       │ config     │      │ config   │
    └───────────┘       └────────────┘      └──────────┘
      CONFIG              CONFIG              CONFIG
```

## Stage Descriptions

| Stage | Purpose | Input | Output | Volume |
|-------|---------|-------|--------|--------|
| **Search** | Query PubMed API for recent stroke literature within the configured date window | Schedule trigger (cron) | PubmedRecord@retrieved | ~40-110/run |
| **Filter** | Two-pass aggressive filtering: rule-based cut (study type, language, MeSH) then LLM triage for clinical relevance | PubmedRecord@retrieved | PubmedRecord@filtered | ~40-110 → ~30-80 → ~4-10 |
| **Summarize** | Generate stroke-domain clinical summaries using an LLM with a specialized prompt | PubmedRecord@filtered | LiteratureSummary@summarized | ~4-10/run |
| **Distribute** | Publish digest to blog (gh-pages) then assemble email digest with blog links | LiteratureSummary@summarized | BlogPage@published, EmailDigest@assembled | 1 blog page + 1 email digest/run |

## Shared Definitions

### Flowing (transformed by stages)

| Definition | Description | Statuses |
|------------|-------------|----------|
| `pubmed-record` | Core domain object: PMID, title, authors, abstract, journal, MeSH terms, article type, publication date | `@retrieved`, `@filtered` |
| `literature-summary` | One per filtered paper: structured summary (objective, methods, key finding, clinical relevance), feedback link | `@summarized` |
| `blog-page` | Rendered Jekyll page with per-article anchors, pushed to `gh-pages` | `@published` |
| `email-digest` | Assembled digest: opening, ordered summaries with blog links, closing | `@assembled` |

### Config (read by stages, changed by users)

| Definition | Description | Used by |
|------------|-------------|---------|
| `search-config` | PubMed query terms, MeSH terms, date window, API key | Search |
| `filter-config` | Include/exclude study types, journal list, language, LLM triage prompt and threshold | Filter |
| `summary-config` | LLM prompt template, output sections, tone, length constraints | Summarize |
| `blog-config` | Site title, base URL, publish toggle, template paths | Distribute (blog-publish) |
| `distribute-config` | Digest title, opening/closing text, sort order, output paths | Distribute (digest-build) |
| (feedback form config lives in `summary-config`, where per-article URLs are constructed) | | |

## Essentials

| Cost | Essential | Detail |
|------|-----------|--------|
| **HIGH** | Core domain object (`pubmed-record`) | Its shape is the pipeline's spine — every stage reads or transforms it. Get the fields right before writing stage code. |
| **HIGH** | Summarization prompt | The LLM prompt for stroke-domain summaries IS the product. Quality here determines whether the digest is useful to clinicians. |
| **MODERATE** | Filter calibration | The rule + LLM triage boundary. Too aggressive = miss practice-changing papers. Too permissive = noise. Target: ~5 articles/week. |
| **MODERATE** | Config surface design | Users configure via YAML without seeing internals. The config schema is a user-facing API — changing it later breaks forks. |
| **EASY TO MISS** | Google Form feedback loop | Each article needs a unique pre-filled URL (`?entry.FIELD_ID=PMID`). Must be part of the summary template, not an afterthought. |
| **EASY TO MISS** | PubMed API rate limits | 3 req/sec without API key, 10 with. Query syntax for MeSH terms has gotchas (e.g., [MeSH Major Topic] vs [MeSH Terms]). |

## Recommended Spikes

### Spike 1: Summarization quality (HIGH)

- **What:** Take 10 real PubMed stroke abstracts from the past week. Write 3 prompt variations (structured extract, narrative, hybrid). Run all 30 and evaluate.
- **Question:** Which prompt structure produces summaries a stroke clinician would find useful?
- **Success:** Summaries let you immediately tell which papers matter and why, without re-reading the abstract.

### Spike 2: Core domain object shape (HIGH)

- **What:** Pull 20 PubMed records via E-utilities. Map the raw XML/JSON to the proposed `pubmed-record` schema. Verify all fields needed by downstream stages.
- **Question:** Does PubMed's API return everything the filter and summarizer need?
- **Success:** Real records map cleanly to the schema with no missing fields or awkward transformations.

### Spike 3: Filter calibration (MODERATE)

- **What:** Take a week's worth of PubMed stroke results (~200). Manually classify 20 as "practice-changing" or not. Run rule-based filter then LLM triage. Compare.
- **Question:** Can the two-pass filter hit ~5/week without missing papers you'd hand-pick?
- **Success:** Filter output matches manual picks with ≤1 false negative.

## Scope Fence (v1)

**In scope:** PubMed abstract-only pipeline, GitHub Actions scheduling, GitHub Pages blog archive, single recipient (comms person), YAML configuration, Google Form feedback, public repo.

**Out of scope:** Interactive web UI, historical backfill, full-text PDF analysis, direct mass email, multi-user accounts.

## Decisions and Rationale

| ID | Decision | Alternatives | Rationale | Date |
|----|----------|-------------|-----------|------|
| A1 | Pipeline archetype with temporal stage grouping | Library/hub-and-spoke; monolithic script | Data flows linearly through transformation stages — pipeline is the natural fit. Monolithic script doesn't scale to configurable stages. | 2026-03-23 |
| A2 | Hybrid filter: rule-based then LLM triage | Rules-only; LLM-only | Rules are free and fast for coarse filtering (study type, language). LLM catches nuance (clinical relevance) on the ~30 survivors. Pure LLM wastes tokens on obvious exclusions. | 2026-03-23 |
| A3 | YAML config files as user-facing API | Environment variables; JSON; Python config objects | YAML is human-readable, diff-friendly, and familiar to non-developers. Config files are the only thing fork users need to edit. | 2026-03-23 |
| A4 | GitHub Actions for scheduling | Local cron; AWS Lambda; GCP Cloud Run | Free for public repos, zero infra for fork users, built-in secrets management. Acceptable trade-off: 6-hour minimum schedule granularity (weekly is fine). | 2026-03-23 |
| A5 | Paste-ready digest in v1 (comms person copies into email) | Automated SMTP; API-based email service | Removes email deliverability complexity from v1. Comms person handles distribution using their existing tooling. Automated sending deferred to future phase. | 2026-03-23 |
| A6 | Google Form with pre-filled PMID for feedback | Custom endpoint; GitHub Issues; email reply | Zero infrastructure. Pre-filled PMID links feedback to specific articles. Responses land in a Google Sheet for analysis. Can upgrade later. | 2026-03-23 |
| A7 | GitHub Pages for blog archive | Ghost; WordPress; Notion | Already on GitHub Actions — blog publish is a git push to `gh-pages`. Free, markdown-native, zero additional infrastructure. Jekyll is built-in. | 2026-03-23 |
| A8 | User-editable blog templates in config/ | Hardcoded in Python; Jinja2 | Templates as config files preserve the code-vs-config separation. Simple placeholder substitution avoids adding Jinja2 as a dependency. | 2026-03-23 |
| A9 | Resend for email delivery | SendGrid; AWS SES; SMTP | Simplest API, generous free tier (100 emails/day), single sender email verification. No DNS changes needed to start with test sender. | 2026-03-23 |

## Phase Map

| Phase | Specs | Goal |
|-------|-------|------|
| Phase 0 | project-infrastructure, test-infrastructure | Bootstrap project structure, CI, and test framework |
| Phase 1 | pubmed-query, rule-filter, llm-triage | Search and filter stages — the data acquisition half of the pipeline |
| Phase 2 | llm-summarize, digest-build | Summarize and distribute stages — the output half |
| Phase 3 | blog-publish, email-send | Blog archive on GitHub Pages + automated email delivery via Resend |

## Dependency Graph

```
Phase 0:
  1. project-infrastructure (no dependencies)
  2. test-infrastructure (no dependencies)

Phase 1:
  3. pubmed-query (no cross-spec dependencies)
  4. rule-filter (needs pubmed-record definition from search stage)
  5. llm-triage (needs rule-filter output)

Phase 2:
  6. llm-summarize (needs pubmed-record@filtered)
  7. digest-build (needs literature-summary@summarized)

Phase 3:
  8. blog-publish (needs literature-summary@summarized; digest-build updated to accept blog URLs)
  9. email-send (needs email-digest@assembled)
```
