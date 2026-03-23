---
name: summarize
owner: architecture
---

# Summarize

## Purpose

Generate stroke-domain clinical summaries for each filtered publication using an LLM with a specialized prompt. This is the pipeline's core value — the summary quality determines whether the digest is useful to clinicians.

## Boundaries

**Input:** `pubmed-record@filtered` (~5 records)

**Output:** `literature-summary@summarized` — one structured summary per paper, including a per-article feedback link

## Member Specs

| Spec | Responsibility |
|------|---------------|
| llm-summarize | Send each filtered abstract to LLM with stroke-domain summary prompt; produce structured output (objective, methods, key finding, clinical relevance); generate Google Form feedback URL with pre-filled PMID |

## Internal Structure

Single spec. Each filtered record is summarized independently — no ordering dependency between individual summaries. Parallelization is possible if needed for performance.

## Boundary Definitions

| Definition | Access |
|------------|--------|
| `summary-config` | reads — LLM prompt template, output sections, tone, length constraints, feedback form settings |
| `pubmed-record` | reads `@filtered` |
| `literature-summary` | writes `@summarized` |

## Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| SM1 | One LLM call per article rather than batch summarization | Individual calls allow per-article error handling and retry. At ~5 articles/run, the overhead is negligible. Batch prompts risk quality degradation when context gets long. |
| SM2 | Feedback link is generated at summarization time, not distribution time | The link is per-article (PMID-specific), so it belongs with the summary. The distribute stage just includes what's already there. |
