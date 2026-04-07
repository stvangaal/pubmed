# PubMed Clinical Literature Monitor — Architecture

## Architecture Owner

The project maintainer (currently @stvangaal). Final authority over shared definitions, pipeline stage boundaries, and configuration surface design.

## Overview

A weekly automated pipeline that identifies practice-changing clinical publications from PubMed across configurable domains (stroke, neurology, etc.), summarizes them using an LLM, and delivers a curated digest for distribution to clinical audiences. Each domain is an isolated config package under `config/domains/{name}/` with its own search terms, filter rules, prompts, and output paths.

**Users:** Clinicians and researchers who receive domain-specific weekly digests. Domain operators (1-2 per domain) who configure search terms, filter rules, and prompts. Maintainers who manage the pipeline infrastructure.

**External dependencies:** PubMed E-utilities API (search and fetch), an LLM API (filtering triage and summarization), GitHub Pages (blog archive), Resend API (email delivery), Kit.com API (optional subscriber-filtered broadcasts via Liquid conditionals), Google Forms (per-article feedback capture).

**Autonomy:** Runs weekly via GitHub Actions on a cron schedule. No human intervention required for normal operation.

**Distribution model:** Public GitHub repo. Users fork and configure via YAML files without modifying source code.

## Pipeline Diagram

```
  --domain stroke
         │
         ▼
  ┌──────────────────┐
  │ Domain Config    │──── config/domains/stroke/
  │ Resolver         │     ├── domain.yaml (schema version)
  └──────┬───────────┘     ├── search-config.yaml
         │                 ├── filter-config.yaml
         │                 ├── summary-config.yaml
         │                 ├── distribute-config.yaml
         │                 ├── blog-config.yaml
         │                 ├── email-config.yaml
         │                 └── prompts/
         ▼
   (feeds all CONFIG boxes below)

  GitHub Actions cron                         GitHub Pages
  (Monday noon ET / 16:00 UTC)                (auto-deploy)
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
| **Search** | Query PubMed API for recent literature using MeSH terms (indexed articles) and Title/Abstract text (preindex articles in priority journals) | Schedule trigger (cron) | PubmedRecord@retrieved | ~40-130/run |
| **Filter** | Two-pass aggressive filtering: rule-based cut (study type, language, MeSH) then LLM triage for clinical relevance | PubmedRecord@retrieved | PubmedRecord@filtered | ~40-110 → ~30-80 → ~4-10 |
| **Summarize** | Generate domain-specific clinical summaries using an LLM with a specialized prompt | PubmedRecord@filtered | LiteratureSummary@summarized | ~4-10/run |
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

All config definitions can be **domain-scoped**: when `--domain` is specified, configs load from `config/domains/{domain}/` instead of `config/`. See decision A10.

| Definition | Description | Used by |
|------------|-------------|---------|
| `search-config` | PubMed query terms, MeSH terms, date window, API key | Search |
| `filter-config` | Include/exclude study types, journal list, language, LLM triage prompt and threshold, per-domain dedup path. `priority_journals` also used by Search stage for preindex queries. | Filter, Search (preindex) |
| `summary-config` | LLM prompt template, output sections, tone, length constraints, subdomain taxonomy | Summarize |
| `blog-config` | Site title, base URL, publish toggle, template paths (global templates, domain-overridable) | Distribute (blog-publish) |
| `distribute-config` | Digest title, opening/closing text, sort order, output paths | Distribute (digest-build) |
| `email-config` | Sender, recipients, subject template | Distribute (email-send) |
| (feedback form config lives in `summary-config`, where per-article URLs are constructed) | | |

## Essentials

| Cost | Essential | Detail |
|------|-----------|--------|
| **HIGH** | Core domain object (`pubmed-record`) | Its shape is the pipeline's spine — every stage reads or transforms it. Get the fields right before writing stage code. |
| **HIGH** | Summarization prompt | The LLM prompt for domain-specific summaries IS the product. Quality here determines whether the digest is useful to clinicians. Each domain needs its own prompt — this is the primary onboarding cost. |
| **MODERATE** | Filter calibration | The rule + LLM triage boundary. Too aggressive = miss practice-changing papers. Too permissive = noise. Target: ~5 articles/week. |
| **MODERATE** | Config surface design | Users configure via YAML without seeing internals. The config schema is a user-facing API — changing it later breaks forks. |
| **EASY TO MISS** | Google Form feedback loop | Each article needs a unique pre-filled URL (`?entry.FIELD_ID=PMID`). Must be part of the summary template, not an afterthought. |
| **EASY TO MISS** | PubMed API rate limits | 3 req/sec without API key, 10 with. Query syntax for MeSH terms has gotchas (e.g., [MeSH Major Topic] vs [MeSH Terms]). |

## Spikes (Completed)

### Spike 1: Summarization quality (HIGH) — DONE

- **Result:** Hybrid prompt (structured extract with narrative key finding) selected. Per-domain prompts stored in `config/domains/{name}/prompts/summary-prompt.md`. See `spikes/summarization/spike_summarize.py` for comparison data.

### Spike 2: Core domain object shape (HIGH) — DONE

- **Result:** PubMed E-utilities XML maps cleanly to `PubmedRecord` dataclass. All fields needed by downstream stages are available. Mixed-content titles handled via `itertext()`. See `spikes/search/spike_search.py`.

### Spike 3: Filter calibration (MODERATE) — DONE

- **Result:** Two-pass filter (rule + LLM at 0.70 threshold) achieves ~5-10 articles/week with acceptable precision. Backfill mechanism (`min_articles`, `min_score_floor`) prevents empty digests. See `spikes/filter/spike_filter_v2.py`.

## Scope Fence

**In scope:** PubMed abstract-only pipeline, GitHub Actions scheduling, GitHub Pages blog archive, multi-domain config packages, YAML configuration, Google Form feedback, automated email delivery via Resend, public repo.

**Out of scope (planned):** Tag-based digest personalization ([#4](https://github.com/stvangaal/pubmed/issues/4)), domain-specific web distribution via WordPress or other CMS ([#5](https://github.com/stvangaal/pubmed/issues/5)).

**Out of scope (no plans):** Interactive web UI, historical backfill, full-text PDF analysis, multi-user accounts.

## Extension Points

Architecture decisions for the current scope deliberately leave room for planned future work:

| Extension | Hook Point | Future Story |
|-----------|-----------|--------------|
| Tag-based personalization | `summary-config.subdomain_options` defines the tag taxonomy per domain. `digest-build` can filter summaries by subscriber tags before rendering. `LiteratureSummary.subdomain` evolves to `tags: list[str]`. | [#4](https://github.com/stvangaal/pubmed/issues/4) |
| External web distribution | `blog-config` gains a `target` field to select the distribution backend (GitHub Pages, WordPress, custom). `blog_publish.py` dispatches to a distribution adapter. | [#5](https://github.com/stvangaal/pubmed/issues/5) |
| Subscriber data source | `email-config.to_addresses` is currently a static list. Future: `source` field selects static / site API / CSV for subscriber data. | [#5](https://github.com/stvangaal/pubmed/issues/5) |

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
| A10 | Domain-scoped config: each domain is a directory under `config/domains/{name}/` with all 6 config YAMLs + prompts, selected via `--domain` CLI arg. Schema versioned via `domain.yaml`. One cron run per domain (matrix strategy). | Single config with domain prefixes; env var switching; database-backed config | Directory-per-domain gives full isolation. Each domain is self-contained and copyable. `_template/` makes onboarding mechanical — no code changes needed to add a domain. Schema versioning is advisory (WARNING log, non-fatal). Global settings (API keys, rate limits, blog templates) remain shared. | 2026-03-24 |
| A11 | Parallel preindex Title/Abstract search limited to priority journals for pre-MeSH articles. MeSH search uses `[Date - MeSH Date]`; preindex uses `[Date - Entry]`. | Wider MeSH query; OR text terms into MeSH query; separate pipeline stage | Top-tier journals appear in PubMed before MeSH indexing (days to weeks). A parallel text search catches these early without polluting the precise MeSH query. Different date fields align each query with when its terms become matchable. Journal limitation keeps noise manageable. `seen_pmids.json` suppresses duplicates across runs. | 2026-04-02 |

## Phase Map

| Phase | Specs | Goal |
|-------|-------|------|
| Phase 0 | project-infrastructure | Bootstrap project structure: shared models, config loading, pipeline orchestrator |
| Phase 1 | pubmed-query, rule-filter, llm-triage | Search and filter stages — the data acquisition half of the pipeline |
| Phase 2 | llm-summarize, digest-build | Summarize and distribute stages — the output half |
| Phase 3 | blog-publish, email-send | Blog archive on GitHub Pages + automated email delivery via Resend |
| Phase 4 | domain-config, stroke-migration (disposable), neurology-setup | Multi-domain infrastructure — domain-scoped config packages, `--domain` CLI, schema versioning. Active domains: stroke, neurology |

## Dependency Graph

```
Phase 0:
  1. project-infrastructure (no dependencies)

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

Phase 4:
  10. domain-config (depends on project-infrastructure for config.py and pipeline.py)
  11. stroke-migration [disposable] (depends on domain-config for the target layout)
  12. neurology-setup (depends on domain-config for the target layout)
```
