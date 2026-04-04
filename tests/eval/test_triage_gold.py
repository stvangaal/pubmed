# owner: ai-evaluation
"""Gold standard agreement tests for LLM triage scoring.

Fetches articles by PMID from PubMed, runs LLM triage, and compares
scores to expert labels.  Requires ANTHROPIC_API_KEY.
"""

import json
import tempfile

import pytest

from tests.eval.conftest import requires_api_key
from tests.eval.pubmed_fetch import fetch_records
from src.filter.llm_triage import llm_triage, _call_llm, _build_user_message, _parse_response
from src.models import LLMTriageConfig, LLMUsage

import anthropic


def _score_articles(records, config):
    """Score articles individually using the triage LLM, returning {pmid: score}."""
    prompt_text = open(config.triage_prompt_file).read()
    if config.use_prompt_caching:
        system_message = [
            {"type": "text", "text": prompt_text, "cache_control": {"type": "ephemeral"}}
        ]
    else:
        system_message = prompt_text

    client = anthropic.Anthropic()
    usage = LLMUsage(stage="eval-triage", model=config.model)
    scores = {}
    for record in records:
        user_content = _build_user_message(record)
        score, rationale = _call_llm(client, config, system_message, user_content, usage)
        scores[record.pmid] = score
    return scores


@pytest.mark.eval
@requires_api_key
class TestTriageGoldStandard:
    """Agreement metrics between LLM triage and expert labels."""

    def test_agreement_metrics(self, gold_triage_data):
        """Compute Cohen's kappa and Spearman correlation against expert labels."""
        articles = gold_triage_data["articles"]
        pmids = [a["pmid"] for a in articles]

        # Fetch article content from PubMed
        records = fetch_records(pmids)
        fetched_pmids = {r.pmid for r in records}
        articles = [a for a in articles if a["pmid"] in fetched_pmids]

        if len(articles) < 10:
            pytest.skip(f"Only {len(articles)} articles fetchable, need >= 10")

        # Score with LLM
        config = LLMTriageConfig()
        llm_scores = _score_articles(records, config)

        # Build parallel lists
        expert_scores = []
        llm_score_list = []
        expert_binary = []
        llm_binary = []

        for article in articles:
            pmid = article["pmid"]
            if pmid not in llm_scores:
                continue
            expert_scores.append(article["expert_score"])
            llm_score_list.append(llm_scores[pmid])
            expert_binary.append(1 if article["expert_label"] == "include" else 0)
            llm_binary.append(1 if llm_scores[pmid] >= 0.70 else 0)

        # Cohen's kappa (binary)
        kappa = _cohens_kappa(expert_binary, llm_binary)
        # Spearman rank correlation
        rho = _spearman(expert_scores, llm_score_list)

        # Report
        print(f"\n=== Triage Gold Standard Results ===")
        print(f"Articles evaluated: {len(expert_scores)}")
        print(f"Cohen's kappa (binary): {kappa:.3f} (target >= 0.70)")
        print(f"Spearman rho: {rho:.3f} (target >= 0.75)")

        # Check for false negatives on practice-changing articles
        false_negatives = []
        for article in articles:
            pmid = article["pmid"]
            if (
                article.get("expert_category") == "practice-changing"
                and pmid in llm_scores
                and llm_scores[pmid] < 0.70
            ):
                false_negatives.append(
                    f"PMID {pmid}: expert=practice-changing, LLM={llm_scores[pmid]:.2f}"
                )

        if false_negatives:
            print(f"\nFALSE NEGATIVES on practice-changing articles:")
            for fn in false_negatives:
                print(f"  {fn}")

        # Assertions
        assert kappa >= 0.50, f"Cohen's kappa {kappa:.3f} below red-flag threshold 0.50"
        assert rho >= 0.60, f"Spearman rho {rho:.3f} below red-flag threshold 0.60"
        assert len(false_negatives) == 0, (
            f"{len(false_negatives)} practice-changing articles missed: {false_negatives}"
        )

        # Soft targets (warn but don't fail)
        if kappa < 0.70:
            print(f"WARNING: kappa {kappa:.3f} below target 0.70")
        if rho < 0.75:
            print(f"WARNING: Spearman {rho:.3f} below target 0.75")


def _cohens_kappa(y1: list[int], y2: list[int]) -> float:
    """Compute Cohen's kappa for binary agreement."""
    n = len(y1)
    if n == 0:
        return 0.0

    # Observed agreement
    agree = sum(1 for a, b in zip(y1, y2) if a == b)
    po = agree / n

    # Expected agreement by chance
    p1_pos = sum(y1) / n
    p2_pos = sum(y2) / n
    pe = p1_pos * p2_pos + (1 - p1_pos) * (1 - p2_pos)

    if pe == 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def _spearman(x: list[float], y: list[float]) -> float:
    """Compute Spearman rank correlation coefficient."""
    n = len(x)
    if n < 3:
        return 0.0

    def _rank(values):
        indexed = sorted(enumerate(values), key=lambda iv: iv[1])
        ranks = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j < n - 1 and indexed[j + 1][1] == indexed[j][1]:
                j += 1
            avg_rank = (i + j) / 2 + 1
            for k in range(i, j + 1):
                ranks[indexed[k][0]] = avg_rank
            i = j + 1
        return ranks

    rx = _rank(x)
    ry = _rank(y)

    d_sq = sum((a - b) ** 2 for a, b in zip(rx, ry))
    return 1 - (6 * d_sq) / (n * (n ** 2 - 1))
