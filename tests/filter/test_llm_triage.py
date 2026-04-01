# owner: llm-triage
"""Tests for the LLM triage backfill (min_articles) logic.

These tests mock _call_llm to avoid real API calls and focus on the
threshold-split, cap, and backfill behaviour.
"""

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from src.filter.llm_triage import llm_triage
from src.models import LLMTriageConfig, PubmedRecord


def _make_record(pmid: str, title: str = "Test") -> PubmedRecord:
    """Create a minimal PubmedRecord for testing."""
    return PubmedRecord(
        pmid=pmid,
        title=title,
        authors=[],
        journal="Test Journal",
        abstract="Test abstract.",
        pub_date="2026-01-01",
        article_types=["journal article"],
        mesh_terms=[],
        language="eng",
        doi=None,
        status="retrieved",
    )


def _make_config(**overrides) -> LLMTriageConfig:
    """Create a LLMTriageConfig pointing at a temp prompt file."""
    defaults = dict(
        model="test-model",
        max_tokens=150,
        score_threshold=0.70,
        max_articles=15,
        min_articles=0,
        min_score_floor=0.50,
        use_prompt_caching=False,
        triage_prompt_file="",  # will be set per-test
        seen_pmids_file="",  # will be set per-test
    )
    defaults.update(overrides)
    return LLMTriageConfig(**defaults)


def _mock_call_llm_factory(score_map: dict[str, float]):
    """Return a _call_llm replacement that returns scores from a mapping.

    score_map: {pmid: score}.  The mock looks up the record's PMID from
    the user_content string (first line: "Title: ...") — but since we
    control _build_user_message, we just return scores in order.
    """
    call_idx = {"i": 0}
    pmid_order: list[str] = list(score_map.keys())

    def _mock(client, config, system_message, user_content, usage_tracker=None):
        # Records are sorted by prompt key, so order may vary.
        # Parse PMID from user_content title line to look up score.
        # user_content starts with "Title: <title>"
        # We embedded the PMID in the title for easy lookup.
        for pmid, score in score_map.items():
            if pmid in user_content:
                return score, f"rationale for {pmid}"
        return 0.0, "unknown"

    return _mock


@pytest.fixture
def tmp_dirs():
    """Provide temp directories for prompt file and seen-pmids."""
    with tempfile.TemporaryDirectory() as tmpdir:
        prompt_file = os.path.join(tmpdir, "triage-prompt.md")
        with open(prompt_file, "w") as f:
            f.write("You are a test scorer. Return JSON: {score, rationale}")
        seen_file = os.path.join(tmpdir, "seen-pmids.json")
        yield tmpdir, prompt_file, seen_file


class TestBackfillMinArticles:
    """Tests for the min_articles backfill logic."""

    def test_no_backfill_when_disabled(self, tmp_dirs):
        """min_articles=0 (default): no backfill, same as before."""
        tmpdir, prompt_file, seen_file = tmp_dirs
        records = [_make_record(f"R{i}", title=f"R{i}") for i in range(5)]
        # All score below threshold
        scores = {f"R{i}": 0.60 for i in range(5)}
        config = _make_config(
            min_articles=0,
            triage_prompt_file=prompt_file,
            seen_pmids_file=seen_file,
        )

        with patch(
            "src.filter.llm_triage._call_llm",
            side_effect=_mock_call_llm_factory(scores),
        ):
            above, below, _ = llm_triage(records, config, seen_pmids_path=seen_file)

        assert len(above) == 0
        assert len(below) == 5

    def test_backfill_triggers(self, tmp_dirs):
        """min_articles=5 with 2 above threshold → backfill 3 from below."""
        tmpdir, prompt_file, seen_file = tmp_dirs
        scores = {
            "A1": 0.85,
            "A2": 0.75,
            "B1": 0.68,
            "B2": 0.65,
            "B3": 0.62,
            "B4": 0.58,
            "B5": 0.55,
        }
        records = [_make_record(pmid, title=pmid) for pmid in scores]
        config = _make_config(
            score_threshold=0.70,
            min_articles=5,
            min_score_floor=0.50,
            triage_prompt_file=prompt_file,
            seen_pmids_file=seen_file,
        )

        with patch(
            "src.filter.llm_triage._call_llm",
            side_effect=_mock_call_llm_factory(scores),
        ):
            above, below, _ = llm_triage(records, config, seen_pmids_path=seen_file)

        assert len(above) == 5
        assert len(below) == 2
        # Top 2 are original above-threshold, next 3 are backfilled
        above_pmids = [r.pmid for r in above]
        assert above_pmids[0] == "A1"
        assert above_pmids[1] == "A2"
        # Backfilled should be B1, B2, B3 (highest below-threshold)
        assert set(above_pmids[2:]) == {"B1", "B2", "B3"}

    def test_floor_respected(self, tmp_dirs):
        """Articles below min_score_floor are never backfilled."""
        tmpdir, prompt_file, seen_file = tmp_dirs
        scores = {
            "A1": 0.80,
            "B1": 0.55,  # above floor (0.50)
            "B2": 0.45,  # below floor
            "B3": 0.40,  # below floor
            "B4": 0.30,  # below floor
        }
        records = [_make_record(pmid, title=pmid) for pmid in scores]
        config = _make_config(
            score_threshold=0.70,
            min_articles=5,
            min_score_floor=0.50,
            triage_prompt_file=prompt_file,
            seen_pmids_file=seen_file,
        )

        with patch(
            "src.filter.llm_triage._call_llm",
            side_effect=_mock_call_llm_factory(scores),
        ):
            above, below, _ = llm_triage(records, config, seen_pmids_path=seen_file)

        # Only A1 (above threshold) + B1 (backfilled) = 2, not 5
        assert len(above) == 2
        assert above[0].pmid == "A1"
        assert above[1].pmid == "B1"
        # Remaining below: B2, B3, B4 (below floor, not eligible)
        assert len(below) == 3

    def test_no_backfill_when_already_sufficient(self, tmp_dirs):
        """When above-threshold already meets min_articles, no backfill."""
        tmpdir, prompt_file, seen_file = tmp_dirs
        scores = {
            "A1": 0.90,
            "A2": 0.85,
            "A3": 0.80,
            "A4": 0.75,
            "A5": 0.72,
            "B1": 0.60,
        }
        records = [_make_record(pmid, title=pmid) for pmid in scores]
        config = _make_config(
            score_threshold=0.70,
            min_articles=3,
            min_score_floor=0.50,
            triage_prompt_file=prompt_file,
            seen_pmids_file=seen_file,
        )

        with patch(
            "src.filter.llm_triage._call_llm",
            side_effect=_mock_call_llm_factory(scores),
        ):
            above, below, _ = llm_triage(records, config, seen_pmids_path=seen_file)

        assert len(above) == 5  # all >= 0.70
        assert len(below) == 1
        # No backfill prefix on any rationale
        for r in above:
            assert "[Backfilled" not in (r.triage_rationale or "")

    def test_rationale_prefix_on_backfilled(self, tmp_dirs):
        """Backfilled articles get a rationale prefix."""
        tmpdir, prompt_file, seen_file = tmp_dirs
        scores = {"A1": 0.80, "B1": 0.65, "B2": 0.60}
        records = [_make_record(pmid, title=pmid) for pmid in scores]
        config = _make_config(
            score_threshold=0.70,
            min_articles=3,
            min_score_floor=0.50,
            triage_prompt_file=prompt_file,
            seen_pmids_file=seen_file,
        )

        with patch(
            "src.filter.llm_triage._call_llm",
            side_effect=_mock_call_llm_factory(scores),
        ):
            above, below, _ = llm_triage(records, config, seen_pmids_path=seen_file)

        assert len(above) == 3
        # A1 should NOT have backfill prefix
        assert "[Backfilled" not in above[0].triage_rationale
        # B1 and B2 should have backfill prefix
        for r in above[1:]:
            assert r.triage_rationale.startswith("[Backfilled to meet 3-article minimum]")

    def test_below_list_excludes_backfilled(self, tmp_dirs):
        """Backfilled articles are removed from the below_threshold list."""
        tmpdir, prompt_file, seen_file = tmp_dirs
        scores = {"A1": 0.80, "B1": 0.65, "B2": 0.60, "B3": 0.55, "C1": 0.40}
        records = [_make_record(pmid, title=pmid) for pmid in scores]
        config = _make_config(
            score_threshold=0.70,
            min_articles=3,
            min_score_floor=0.50,
            triage_prompt_file=prompt_file,
            seen_pmids_file=seen_file,
        )

        with patch(
            "src.filter.llm_triage._call_llm",
            side_effect=_mock_call_llm_factory(scores),
        ):
            above, below, _ = llm_triage(records, config, seen_pmids_path=seen_file)

        above_pmids = {r.pmid for r in above}
        below_pmids = {r.pmid for r in below}

        # A1 (above thresh) + B1, B2 (backfilled) = 3 above
        assert above_pmids == {"A1", "B1", "B2"}
        # B3 (eligible but not needed) + C1 (below floor) remain
        assert below_pmids == {"B3", "C1"}

    def test_above_sorted_after_backfill(self, tmp_dirs):
        """Above-threshold list is sorted by score desc after backfill."""
        tmpdir, prompt_file, seen_file = tmp_dirs
        scores = {"A1": 0.80, "B1": 0.68, "B2": 0.65}
        records = [_make_record(pmid, title=pmid) for pmid in scores]
        config = _make_config(
            score_threshold=0.70,
            min_articles=3,
            min_score_floor=0.50,
            triage_prompt_file=prompt_file,
            seen_pmids_file=seen_file,
        )

        with patch(
            "src.filter.llm_triage._call_llm",
            side_effect=_mock_call_llm_factory(scores),
        ):
            above, below, _ = llm_triage(records, config, seen_pmids_path=seen_file)

        scores_in_order = [r.triage_score for r in above]
        assert scores_in_order == sorted(scores_in_order, reverse=True)
