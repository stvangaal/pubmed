# owner: ai-evaluation
---
name: ai-evaluation
status: draft
owner: filter
owns:
  - tests/eval/__init__.py
  - tests/eval/conftest.py
  - tests/eval/pubmed_fetch.py
  - tests/eval/score_distribution.py
  - tests/eval/summary_completeness.py
  - tests/eval/test_triage_gold.py
  - tests/eval/test_summary_gold.py
  - tests/eval/test_retest_reliability.py
  - tests/eval/test_regression.py
  - tests/eval/gold_standard/triage_gold.json
  - tests/eval/gold_standard/summary_gold.json
  - tests/eval/gold_standard/must_catch.json
  - tests/eval/golden_outputs/.gitkeep
  - tests/eval/eval-workflow.qmd
  - data/eval/.cache/
requires:
  - name: pubmed-record
    version: v0
  - name: filter-config
    version: v0
  - name: summary-config
    version: v0
provides: []
---

# AI Evaluation Framework

## Status
draft

## Target Phase
Phase 5

## Purpose
Measure and monitor the quality, reliability, and calibration of LLM-based triage scoring and summarization. Detect regressions, ensure test-retest reliability, and track coverage/recall to minimize false negatives (the most dangerous failure mode for a clinical literature monitor).

## Requires (Inbound Contracts)

| Dependency | Source | Definition |
|------------|--------|------------|
| Triage-scored PubMed records | llm-triage spec | `pubmed-record` v0 (`@filtered` status) |
| Filter configuration | user config | `filter-config` v0 (`llm_triage` section) |
| Summary configuration | user config | `summary-config` v0 |

## Provides (Outbound Contracts)

None. This spec is a consumer-only evaluation layer.

## Design Constraints

### Copyright: no abstracts in repo
Gold standard datasets store PMIDs and expert labels only. Article content (title, abstract, MeSH terms, etc.) is fetched from PubMed at evaluation runtime via the existing `efetch` + `parse_record` functions. Fetched data is cached locally in `data/eval/.cache/` (gitignored) to avoid redundant API calls.

## Behaviour

### Phase 1: Foundation

#### 1A. Post-run Observability
After each pipeline run, compute and log:
- **Score distribution:** mean, median, std dev, count per tier (0.90+, 0.80-0.89, 0.70-0.79, 0.50-0.69, <0.50), articles-above-threshold
- **Parse success rate:** fraction of summarized articles with successful parse (8/8 fields)
- **Summary completeness:** field presence, sentence count in short_summary, valid tags, valid citation URL

These are zero-cost (no LLM calls) post-processing checks.

#### 1B. Gold Standard Datasets
- **Triage gold** (`tests/eval/gold_standard/triage_gold.json`): 30 PMIDs with expert labels
  - Format: `[{pmid, expert_score, expert_label, expert_category, notes}]`
  - Labels: `expert_label` in {include, exclude}; `expert_category` in {practice-changing, highly-relevant, informative, incremental, low-relevance}
  - Stratified: ~5 per category
- **Summary gold** (`tests/eval/gold_standard/summary_gold.json`): 10 PMIDs with expert ratings
  - Format: `[{pmid, accuracy, completeness, clinical_utility, notes}]` (ratings 1-5)
- **Must-catch** (`tests/eval/gold_standard/must_catch.json`): 5-10 PMIDs of known important publications
  - Format: `[{pmid, domain, notes}]`
  - Updated quarterly

#### 1C. Agreement Metrics
- **Cohen's kappa** (binary include/exclude at 0.70 threshold) — target >= 0.70
- **Spearman rank correlation** between LLM scores and expert scores — target >= 0.75
- Zero false negatives on articles expert-labeled as "practice-changing"

### Phase 2: Reliability & Regression

#### 2A. Test-Retest Reliability
Score 20 articles x 5 runs each. Measure:
- Per-article standard deviation — target <= 0.05
- Intraclass correlation coefficient (ICC) — target >= 0.85
- Threshold-flip rate (fraction crossing 0.70) — target < 10%

#### 2B. Regression Testing
Snapshot gold-dataset scores as baseline. After prompt/model changes:
- No practice-changing article drops below 0.80
- Spearman rank correlation vs baseline >= 0.80
- Mean absolute score difference <= 0.10

### Phase 3: Calibration & Sensitivity (future)

#### 3A. Calibration Analysis
Are scores well-calibrated? Expected calibration error (ECE) <= 0.10.

#### 3B. Prompt Sensitivity
3-5 prompt variants, measure mean score shift. Target <= 0.05.

#### 3C. Input Sensitivity
Test robustness to truncated abstracts, missing MeSH, missing article types. Target <= 0.10 for truncation.

### Phase 4: Coverage & Recall (future)

#### 4A. Below-Threshold Review
Weekly expert scan of `filter-triage-below-threshold.json`. Target: 0 missed practice-changing articles per quarter.

#### 4B. Must-Catch Test
End-to-end recall verification against curated list of known important publications.

## Key Targets

| Metric | Target | Red Flag |
|---|---|---|
| Cohen's kappa (binary) | >= 0.70 | < 0.50 |
| Spearman rank correlation | >= 0.75 | < 0.60 |
| Test-retest std dev | <= 0.05 | > 0.10 |
| Threshold-flip rate | < 10% | > 25% |
| False negatives (practice-changing) | 0/quarter | Any |
| Parse success rate | >= 95% | < 85% |
| Regression Spearman vs baseline | >= 0.80 | < 0.65 |
| Must-catch recall | >= 90% | < 75% |

## Tests

### Unit Tests (no API calls)
- `test_score_distribution`: Verify distribution computation from mock score lists
- `test_summary_completeness`: Verify completeness checks on mock summaries

### Evaluation Tests (`@pytest.mark.eval`, require ANTHROPIC_API_KEY)
- `test_triage_gold`: Gold standard agreement metrics (30 articles)
- `test_summary_gold`: Summary quality on gold articles (10 articles)
- `test_retest_reliability`: Score stability (20 articles x 5 runs)
- `test_regression`: Score regression vs baseline (30 articles)

## Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| AE1 | PMIDs only in repo, fetch at runtime | Copyright: cannot store abstracts in git |
| AE2 | Cache PubMed fetches locally | Avoid redundant API calls during repeated test runs |
| AE3 | Separate pytest markers (eval, regression) | Eval tests require API key and cost money; don't run in standard CI |
| AE4 | Expert labels from project owner | Domain expertise available; no external labeling infrastructure needed |
