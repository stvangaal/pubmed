# owner: ai-evaluation
"""Test-retest reliability for triage scoring.

Scores each gold-standard article multiple times and measures score
stability.  Requires ANTHROPIC_API_KEY.
"""

import statistics

import pytest

import anthropic

from tests.eval.conftest import requires_api_key
from tests.eval.pubmed_fetch import fetch_records
from src.filter.llm_triage import _call_llm, _build_user_message
from src.models import LLMTriageConfig, LLMUsage


N_RUNS = 5
MAX_ARTICLES = 20


@pytest.mark.eval_costly
@requires_api_key
class TestRetestReliability:
    """Score stability across repeated LLM calls."""

    def test_score_stability(self, gold_triage_data):
        """Each article scored N times; measure per-article std dev and ICC."""
        articles = gold_triage_data["articles"][:MAX_ARTICLES]
        pmids = [a["pmid"] for a in articles]

        records = fetch_records(pmids)
        if len(records) < 10:
            pytest.skip(f"Only {len(records)} articles fetchable, need >= 10")

        config = LLMTriageConfig()
        prompt_text = open(config.triage_prompt_file).read()
        system_message = [
            {"type": "text", "text": prompt_text, "cache_control": {"type": "ephemeral"}}
        ]

        client = anthropic.Anthropic()
        usage = LLMUsage(stage="eval-retest", model=config.model)

        # Score each article N_RUNS times
        all_scores: dict[str, list[float]] = {r.pmid: [] for r in records}

        for run in range(N_RUNS):
            for record in records:
                user_content = _build_user_message(record)
                score, _ = _call_llm(client, config, system_message, user_content, usage)
                all_scores[record.pmid].append(score)

        # Compute per-article statistics
        stdevs = []
        flip_rates = []
        all_means = []

        print(f"\n=== Test-Retest Reliability ({N_RUNS} runs x {len(records)} articles) ===")
        print(f"{'PMID':<12} {'Mean':>6} {'StDev':>6} {'Min':>5} {'Max':>5} {'Flips':>5}")
        print("-" * 50)

        for pmid, scores in all_scores.items():
            mean = statistics.mean(scores)
            stdev = statistics.stdev(scores) if len(scores) > 1 else 0.0
            flips = sum(
                1 for s in scores if (s >= 0.70) != (mean >= 0.70)
            )
            flip_rate = flips / len(scores)

            stdevs.append(stdev)
            flip_rates.append(flip_rate)
            all_means.append(mean)

            print(f"{pmid:<12} {mean:>6.3f} {stdev:>6.3f} {min(scores):>5.2f} {max(scores):>5.2f} {flips:>5d}")

        # Aggregate metrics
        mean_stdev = statistics.mean(stdevs)
        max_stdev = max(stdevs)
        icc = _compute_icc(all_scores)
        mean_flip_rate = statistics.mean(flip_rates)

        # Borderline articles (mean 0.65-0.75) — most vulnerable
        borderline = [
            (pmid, fr) for pmid, fr, m in zip(all_scores.keys(), flip_rates, all_means)
            if 0.65 <= m <= 0.75
        ]

        print(f"\n--- Aggregate ---")
        print(f"Mean per-article stdev: {mean_stdev:.4f} (target <= 0.05)")
        print(f"Max per-article stdev:  {max_stdev:.4f}")
        print(f"ICC:                    {icc:.3f} (target >= 0.85)")
        print(f"Mean threshold-flip rate: {mean_flip_rate:.1%} (target < 10%)")
        print(f"Borderline articles (0.65-0.75): {len(borderline)}")
        print(f"LLM cost: ${usage.estimated_cost:.4f}")

        # Assertions (red-flag thresholds)
        assert mean_stdev <= 0.10, f"Mean stdev {mean_stdev:.4f} above red-flag 0.10"
        assert icc >= 0.70, f"ICC {icc:.3f} below red-flag 0.70"

        # Soft targets
        if mean_stdev > 0.05:
            print(f"WARNING: Mean stdev {mean_stdev:.4f} above target 0.05")
        if icc < 0.85:
            print(f"WARNING: ICC {icc:.3f} below target 0.85")
        if mean_flip_rate > 0.10:
            print(f"WARNING: Flip rate {mean_flip_rate:.1%} above target 10%")


def _compute_icc(all_scores: dict[str, list[float]]) -> float:
    """Compute ICC(2,1) — two-way random, single measures.

    Simplified computation treating each run as a rater.
    """
    articles = list(all_scores.values())
    n = len(articles)  # number of subjects (articles)
    if n < 2:
        return 0.0
    k = len(articles[0])  # number of raters (runs)
    if k < 2:
        return 0.0

    # Grand mean
    all_values = [s for scores in articles for s in scores]
    grand_mean = statistics.mean(all_values)

    # Between-subjects sum of squares
    row_means = [statistics.mean(scores) for scores in articles]
    ss_between = k * sum((rm - grand_mean) ** 2 for rm in row_means)

    # Within-subjects sum of squares
    ss_within = sum(
        sum((s - rm) ** 2 for s in scores)
        for scores, rm in zip(articles, row_means)
    )

    # Between-raters sum of squares
    col_means = [
        statistics.mean(articles[i][j] for i in range(n))
        for j in range(k)
    ]
    ss_raters = n * sum((cm - grand_mean) ** 2 for cm in col_means)

    # Residual
    ss_residual = ss_within - ss_raters

    # Mean squares
    ms_between = ss_between / (n - 1) if n > 1 else 0
    ms_residual = ss_residual / ((n - 1) * (k - 1)) if (n > 1 and k > 1) else 0

    # ICC(2,1)
    denominator = ms_between + (k - 1) * ms_residual
    if denominator == 0:
        return 0.0
    return (ms_between - ms_residual) / denominator
