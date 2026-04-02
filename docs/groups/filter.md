---
name: filter
owner: architecture
---

# Filter

## Purpose

Aggressively reduce the candidate set to only practice-changing stroke publications. Uses a two-pass approach: fast rule-based filtering first (free, deterministic), then LLM triage on survivors (nuanced, costs tokens). Target output: ~10 articles per week.

## Boundaries

**Input:** `pubmed-record@retrieved` (~40-130 records, mix of MeSH-indexed and preindex articles)

**Output:** `pubmed-record@filtered` (~10 records, scored and annotated with triage rationale; `preindex` and `source_topic` preserved)

## Member Specs

| Spec | Responsibility |
|------|---------------|
| rule-filter | Apply deterministic filters: study type inclusion/exclusion, journal list, language, MeSH term matching |
| llm-triage | Send surviving abstracts (~150-200) to LLM with stroke-domain triage prompt; score clinical relevance; apply threshold |

## Internal Structure

Sequential within the stage: `rule-filter` runs first, then `llm-triage` scores the ~150-200 survivors (reduces to ~10). This ordering is load-bearing — reversing it would waste LLM tokens on obviously irrelevant papers.

## Boundary Definitions

| Definition | Access |
|------------|--------|
| `filter-config` | reads — study type lists, journal list, language, LLM triage prompt, relevance threshold |
| `pubmed-record` | reads `@retrieved`, writes `@filtered` |

## Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| F1 | Two-pass hybrid filtering (rules then LLM) rather than LLM-only | Rules are free and eliminate obvious non-matches (animal studies, editorials, non-English). LLM tokens are spent only on the ~30 ambiguous survivors where clinical judgment matters. |
| F2 | LLM triage uses the same abstract text as summarization, not a separate fetch | Avoids redundant API calls. The abstract is already in the pubmed-record from the search stage. |
