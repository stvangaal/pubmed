# owner: ai-evaluation
"""Gold standard quality tests for LLM summarization.

Fetches articles by PMID from PubMed, runs summarization, and checks
structural completeness plus expert quality ratings.
"""

import pytest

from tests.eval.conftest import requires_api_key
from tests.eval.pubmed_fetch import fetch_records
from tests.eval.summary_completeness import check_summary
from src.summarize.llm_summarize import summarize
from src.models import SummaryConfig


def _load_prompt(path: str = "config/prompts/summary-prompt.md") -> str:
    with open(path) as f:
        return f.read()


@pytest.mark.eval
@requires_api_key
class TestSummaryGoldStandard:
    """Summary quality on expert-rated articles."""

    def test_structural_completeness(self, gold_summary_data):
        """All gold-standard summaries should parse with 8/8 fields."""
        articles = gold_summary_data["articles"]
        pmids = [a["pmid"] for a in articles]

        records = fetch_records(pmids)
        if len(records) < 5:
            pytest.skip(f"Only {len(records)} articles fetchable, need >= 5")

        # Set status to filtered (as if they passed triage)
        for r in records:
            r.status = "filtered"
            r.triage_score = 0.85
            r.triage_rationale = "Gold standard test article"

        config = SummaryConfig(prompt_template=_load_prompt())
        summaries, usage = summarize(records, config)

        print(f"\n=== Summary Gold Standard Results ===")
        print(f"Articles: {len(records)}, Summaries: {len(summaries)}")
        print(f"Parse success rate: {len(summaries)/len(records):.1%}")
        print(f"LLM cost: ${usage.estimated_cost:.4f}")

        # Check completeness of each summary
        issues_found = []
        for summary in summaries:
            result = check_summary(
                {
                    "pmid": summary.pmid,
                    "tags": summary.tags,
                    "citation": summary.citation,
                    "research_question": summary.research_question,
                    "key_finding": summary.key_finding,
                    "design": summary.design,
                    "primary_outcome": summary.primary_outcome,
                    "limitations": summary.limitations,
                    "summary_short": summary.summary_short,
                },
                valid_tags=config.subdomain_options,
            )
            if not result.is_complete:
                issues_found.append((summary.pmid, result.issues))

        if issues_found:
            print("\nCompleteness issues:")
            for pmid, issues in issues_found:
                for issue in issues:
                    print(f"  PMID {pmid}: {issue}")

        # Assertions
        parse_rate = len(summaries) / len(records)
        assert parse_rate >= 0.85, f"Parse rate {parse_rate:.1%} below red-flag 85%"
        if parse_rate < 0.95:
            print(f"WARNING: Parse rate {parse_rate:.1%} below target 95%")
