# owner: ai-evaluation
"""Regression tests for triage scoring.

Compares current LLM scores against a saved baseline to detect
regressions from prompt or model changes.  Requires ANTHROPIC_API_KEY.
"""

import json
from pathlib import Path

import pytest

import anthropic

from tests.eval.conftest import requires_api_key, GOLDEN_OUTPUTS_DIR
from tests.eval.pubmed_fetch import fetch_records
from tests.eval.test_triage_gold import _spearman, _score_articles
from src.models import LLMTriageConfig


def _latest_baseline() -> Path | None:
    """Find the most recent triage baseline file."""
    baselines = sorted(GOLDEN_OUTPUTS_DIR.glob("triage_baseline_*.json"))
    return baselines[-1] if baselines else None


@pytest.mark.regression
@requires_api_key
class TestTriageRegression:
    """Detect score regressions vs a saved baseline."""

    def test_no_regression(self):
        """Current scores should correlate with baseline and not drop practice-changing articles."""
        baseline_path = _latest_baseline()
        if baseline_path is None:
            pytest.skip("No baseline found in tests/eval/golden_outputs/")

        with open(baseline_path) as f:
            baseline = json.load(f)

        baseline_scores = baseline["scores"]  # {pmid: score}
        pmids = list(baseline_scores.keys())

        # Fetch and score
        records = fetch_records(pmids)
        fetched_pmids = {r.pmid for r in records}
        pmids = [p for p in pmids if p in fetched_pmids]

        if len(pmids) < 10:
            pytest.skip(f"Only {len(pmids)} articles fetchable, need >= 10")

        config = LLMTriageConfig(
            triage_prompt_file=baseline.get(
                "prompt_file", "config/prompts/triage-prompt.md"
            )
        )
        current_scores = _score_articles(records, config)

        # Build parallel lists
        baseline_list = []
        current_list = []
        for pmid in pmids:
            if pmid in current_scores and pmid in baseline_scores:
                baseline_list.append(baseline_scores[pmid])
                current_list.append(current_scores[pmid])

        # Spearman rank correlation
        rho = _spearman(baseline_list, current_list)

        # Mean absolute difference
        diffs = [abs(b - c) for b, c in zip(baseline_list, current_list)]
        mad = sum(diffs) / len(diffs) if diffs else 0.0

        # Practice-changing drops
        practice_changing = baseline.get("practice_changing_pmids", [])
        dropped = [
            f"PMID {pmid}: baseline={baseline_scores[pmid]:.2f}, current={current_scores.get(pmid, 0):.2f}"
            for pmid in practice_changing
            if pmid in current_scores and current_scores[pmid] < 0.80
        ]

        print(f"\n=== Regression Test vs {baseline_path.name} ===")
        print(f"Articles: {len(baseline_list)}")
        print(f"Spearman rho: {rho:.3f} (target >= 0.80)")
        print(f"Mean absolute diff: {mad:.3f} (target <= 0.10)")
        print(f"Practice-changing drops: {len(dropped)}")

        if dropped:
            print("\nPractice-changing articles that dropped below 0.80:")
            for d in dropped:
                print(f"  {d}")

        # Assertions
        assert rho >= 0.65, f"Spearman {rho:.3f} below red-flag 0.65"
        assert len(dropped) == 0, f"Practice-changing articles regressed: {dropped}"

        if rho < 0.80:
            print(f"WARNING: Spearman {rho:.3f} below target 0.80")
        if mad > 0.10:
            print(f"WARNING: MAD {mad:.3f} above target 0.10")


def save_baseline(
    scores: dict[str, float],
    practice_changing_pmids: list[str] | None = None,
    prompt_file: str = "config/prompts/triage-prompt.md",
    model: str = "claude-sonnet-4-6",
) -> Path:
    """Save a triage score baseline for future regression testing.

    Call this after a gold-standard evaluation run to snapshot scores.

    Args:
        scores: {pmid: score} mapping from evaluation.
        practice_changing_pmids: PMIDs of expert-labeled practice-changing articles.
        prompt_file: Path to the prompt used.
        model: Model identifier.

    Returns:
        Path to the saved baseline file.
    """
    from datetime import datetime

    GOLDEN_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = GOLDEN_OUTPUTS_DIR / f"triage_baseline_{date_str}.json"

    baseline = {
        "date": date_str,
        "model": model,
        "prompt_file": prompt_file,
        "article_count": len(scores),
        "practice_changing_pmids": practice_changing_pmids or [],
        "scores": scores,
    }

    with open(path, "w") as f:
        json.dump(baseline, f, indent=2)

    return path
