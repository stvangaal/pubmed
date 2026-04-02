# owner: digest-build
"""Tests for digest building: subdomain grouping and narrative review detection."""

from src.distribute.digest_build import (
    _group_by_subdomain,
    _is_narrative_review,
    _subdomain_label,
)
from src.models import LiteratureSummary


def _make_summary(
    pmid: str = "1",
    tags: list[str] | None = None,
    triage_score: float = 0.85,
    article_types: list[str] | None = None,
) -> LiteratureSummary:
    """Create a minimal LiteratureSummary for testing."""
    return LiteratureSummary(
        pmid=pmid,
        title=f"Test Article {pmid}",
        journal="Test Journal",
        pub_date="2026-01-01",
        tags=tags if tags is not None else ["Prevention"],
        citation=f"Test Article {pmid}. *Test Journal*. [PMID {pmid}](url)",
        research_question="What is tested?",
        key_finding="Testing works.",
        design="Test, N=1",
        primary_outcome="p<0.05",
        limitations="Small sample",
        summary_short="A test. It passed.",
        triage_score=triage_score,
        triage_rationale="Relevant",
        feedback_url="https://example.com/feedback",
        raw_llm_response="raw",
        source_topic="primary",
        preindex=False,
        article_types=article_types or [],
    )


class TestGroupBySubdomain:
    def test_groups_by_subdomain_field(self):
        summaries = [
            _make_summary(pmid="1", tags=["Prevention"]),
            _make_summary(pmid="2", tags=["Imaging"]),
            _make_summary(pmid="3", tags=["Prevention"]),
        ]
        groups = _group_by_subdomain(summaries)
        assert list(groups.keys()) == ["Prevention", "Imaging"]
        assert len(groups["Prevention"]) == 2
        assert len(groups["Imaging"]) == 1

    def test_empty_tags_falls_back_to_general(self):
        summaries = [_make_summary(pmid="1", tags=[])]
        groups = _group_by_subdomain(summaries)
        assert "General" in groups

    def test_preserves_insertion_order(self):
        summaries = [
            _make_summary(pmid="1", tags=["Imaging"]),
            _make_summary(pmid="2", tags=["Acute Treatment"]),
            _make_summary(pmid="3", tags=["Imaging"]),
        ]
        groups = _group_by_subdomain(summaries)
        assert list(groups.keys()) == ["Imaging", "Acute Treatment"]

    def test_groups_by_primary_tag(self):
        """Multi-tag article groups under its primary (first) tag."""
        summaries = [
            _make_summary(pmid="1", tags=["Imaging", "Prevention"]),
            _make_summary(pmid="2", tags=["Prevention"]),
        ]
        groups = _group_by_subdomain(summaries)
        assert list(groups.keys()) == ["Imaging", "Prevention"]
        assert len(groups["Imaging"]) == 1
        assert len(groups["Prevention"]) == 1


class TestSubdomainLabel:
    def test_returns_name_as_is(self):
        assert _subdomain_label("Acute Treatment") == "Acute Treatment"

    def test_empty_returns_general(self):
        assert _subdomain_label("") == "General"


class TestIsNarrativeReview:
    def test_plain_review_is_narrative(self):
        s = _make_summary(article_types=["Journal Article", "Review"])
        assert _is_narrative_review(s) is True

    def test_review_alone_is_narrative(self):
        s = _make_summary(article_types=["Review"])
        assert _is_narrative_review(s) is True

    def test_systematic_review_is_not_narrative(self):
        s = _make_summary(article_types=["Review", "Systematic Review"])
        assert _is_narrative_review(s) is False

    def test_meta_analysis_is_not_narrative(self):
        s = _make_summary(article_types=["Review", "Meta-Analysis"])
        assert _is_narrative_review(s) is False

    def test_no_review_type_is_not_narrative(self):
        s = _make_summary(article_types=["Randomized Controlled Trial"])
        assert _is_narrative_review(s) is False

    def test_empty_types_is_not_narrative(self):
        s = _make_summary(article_types=[])
        assert _is_narrative_review(s) is False

    def test_case_insensitive(self):
        s = _make_summary(article_types=["review"])
        assert _is_narrative_review(s) is True
