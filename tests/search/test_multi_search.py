# owner: pubmed-query
"""Tests for multi_search — multiple independent queries with deduplication."""

from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from src.models import PubmedRecord, SearchConfig, Topic
from src.search.pubmed_query import multi_search, _execute_query


def _make_record(pmid: str, title: str = "") -> PubmedRecord:
    """Create a minimal PubmedRecord for testing."""
    return PubmedRecord(
        pmid=pmid,
        title=title or f"Article {pmid}",
        authors=[],
        journal="Test Journal",
        abstract="Test abstract",
        pub_date="2026-03-20",
        article_types=["Journal Article"],
        mesh_terms=["Stroke"],
        language="eng",
        doi=None,
        status="retrieved",
    )


class TestMultiSearchNoTopics:
    """When topics is empty, multi_search behaves like search."""

    @patch("src.search.pubmed_query.search")
    def test_returns_primary_results(self, mock_search):
        records = [_make_record("1001"), _make_record("1002")]
        mock_search.return_value = (records, 2)

        config = SearchConfig(mesh_terms=["stroke"])
        result, total = multi_search(config, run_date=datetime(2026, 3, 23))

        assert len(result) == 2
        assert total == 2
        mock_search.assert_called_once()

    @patch("src.search.pubmed_query.search")
    def test_empty_primary_returns_empty(self, mock_search):
        mock_search.return_value = ([], 0)

        config = SearchConfig(mesh_terms=["stroke"])
        result, total = multi_search(config)

        assert result == []
        assert total == 0


class TestMultiSearchWithTopics:
    """When topics are configured, results are merged and deduped."""

    @patch("src.search.pubmed_query.search")
    def test_merges_topic_results(self, mock_search):
        primary = [_make_record("1001")]
        topic_results = [_make_record("2001"), _make_record("2002")]
        mock_search.side_effect = [
            (primary, 1),
            (topic_results, 2),
        ]

        config = SearchConfig(
            mesh_terms=["stroke"],
            topics=[
                Topic(name="af", mesh_terms=["atrial fibrillation"]),
            ],
        )
        result, total = multi_search(config, run_date=datetime(2026, 3, 23))

        assert len(result) == 3
        assert total == 3
        assert [r.pmid for r in result] == ["1001", "2001", "2002"]

    @patch("src.search.pubmed_query.search")
    def test_source_topic_tagged_on_records(self, mock_search):
        """Records are tagged with their source topic name."""
        primary = [_make_record("1001")]
        topic_results = [_make_record("2001")]
        mock_search.side_effect = [
            (primary, 1),
            (topic_results, 1),
        ]

        config = SearchConfig(
            mesh_terms=["stroke"],
            topics=[
                Topic(name="af", mesh_terms=["atrial fibrillation"]),
            ],
        )
        result, _ = multi_search(config, run_date=datetime(2026, 3, 23))

        assert result[0].source_topic == "primary"
        assert result[1].source_topic == "af"

    @patch("src.search.pubmed_query.search")
    def test_deduplicates_by_pmid(self, mock_search):
        """Duplicate PMIDs across primary and profile are kept once."""
        primary = [_make_record("1001"), _make_record("1002")]
        profile_results = [_make_record("1002"), _make_record("2001")]
        mock_search.side_effect = [
            (primary, 2),
            (profile_results, 2),
        ]

        config = SearchConfig(
            mesh_terms=["stroke"],
            topics=[
                Topic(name="af", mesh_terms=["atrial fibrillation"]),
            ],
        )
        result, total = multi_search(config, run_date=datetime(2026, 3, 23))

        assert len(result) == 3
        assert [r.pmid for r in result] == ["1001", "1002", "2001"]
        assert total == 4  # total is sum of esearch counts

    @patch("src.search.pubmed_query.search")
    def test_dedup_across_multiple_profiles(self, mock_search):
        """Same PMID appearing in multiple profiles is only included once."""
        primary = [_make_record("1001")]
        profile1 = [_make_record("2001"), _make_record("3001")]
        profile2 = [_make_record("2001"), _make_record("4001")]
        mock_search.side_effect = [
            (primary, 1),
            (profile1, 2),
            (profile2, 2),
        ]

        config = SearchConfig(
            mesh_terms=["stroke"],
            topics=[
                Topic(name="af", mesh_terms=["atrial fibrillation"]),
                Topic(name="cs", mesh_terms=["carotid stenosis"]),
            ],
        )
        result, total = multi_search(config)

        assert len(result) == 4
        assert [r.pmid for r in result] == ["1001", "2001", "3001", "4001"]

    @patch("src.search.pubmed_query.search")
    def test_profile_inherits_parent_config(self, mock_search):
        """Profile queries use parent's date_window, retmax, etc."""
        mock_search.return_value = ([], 0)

        config = SearchConfig(
            mesh_terms=["stroke"],
            date_window_days=14,
            retmax=500,
            require_abstract=False,
            rate_limit_delay=0.1,
            api_key="test-key",
            topics=[
                Topic(name="af", mesh_terms=["atrial fibrillation"]),
            ],
        )
        multi_search(config, run_date=datetime(2026, 3, 23))

        assert mock_search.call_count == 2
        profile_config = mock_search.call_args_list[1][0][0]
        assert profile_config.mesh_terms == ["atrial fibrillation"]
        assert profile_config.date_window_days == 14
        assert profile_config.retmax == 500
        assert profile_config.require_abstract is False
        assert profile_config.rate_limit_delay == 0.1
        assert profile_config.api_key == "test-key"
        assert profile_config.topics == []

    @patch("src.search.pubmed_query.search")
    def test_profile_additional_terms_passed(self, mock_search):
        mock_search.return_value = ([], 0)

        config = SearchConfig(
            mesh_terms=["stroke"],
            topics=[
                Topic(
                    name="af",
                    mesh_terms=["atrial fibrillation"],
                    additional_terms=["anticoagulant"],
                ),
            ],
        )
        multi_search(config)

        profile_config = mock_search.call_args_list[1][0][0]
        assert profile_config.additional_terms == ["anticoagulant"]


class TestMultiSearchPreindex:
    """When preindex_journals is provided, text-based searches run after MeSH."""

    @patch("src.search.pubmed_query._execute_query")
    @patch("src.search.pubmed_query.search")
    def test_preindex_records_tagged(self, mock_search, mock_execute):
        """Preindex-only hits have preindex=True and correct source_topic."""
        mock_search.return_value = ([_make_record("1001")], 1)
        mock_execute.return_value = ([_make_record("2001")], 1)

        config = SearchConfig(mesh_terms=["stroke"])
        result, _ = multi_search(
            config,
            run_date=datetime(2026, 3, 30),
            preindex_journals=["the new england journal of medicine"],
        )

        assert len(result) == 2
        assert result[0].preindex is False
        assert result[1].preindex is True
        assert result[1].source_topic == "primary"

    @patch("src.search.pubmed_query._execute_query")
    @patch("src.search.pubmed_query.search")
    def test_mesh_hit_wins_dedup_over_preindex(self, mock_search, mock_execute):
        """Same PMID from MeSH and preindex — MeSH wins, preindex=False."""
        mock_search.return_value = ([_make_record("1001")], 1)
        mock_execute.return_value = ([_make_record("1001")], 1)

        config = SearchConfig(mesh_terms=["stroke"])
        result, _ = multi_search(
            config,
            run_date=datetime(2026, 3, 30),
            preindex_journals=["jama"],
        )

        assert len(result) == 1
        assert result[0].pmid == "1001"
        assert result[0].preindex is False

    @patch("src.search.pubmed_query._execute_query")
    @patch("src.search.pubmed_query.search")
    def test_preindex_runs_for_topics(self, mock_search, mock_execute):
        """Preindex searches run for each topic, not just primary."""
        primary = [_make_record("1001")]
        topic_mesh = [_make_record("2001")]
        # Two preindex calls: one for primary, one for topic
        preindex_primary = [_make_record("3001")]
        preindex_topic = [_make_record("4001")]
        mock_search.side_effect = [
            (primary, 1),
            (topic_mesh, 1),
        ]
        mock_execute.side_effect = [
            (preindex_primary, 1),
            (preindex_topic, 1),
        ]

        config = SearchConfig(
            mesh_terms=["stroke"],
            topics=[Topic(name="af", mesh_terms=["atrial fibrillation"])],
        )
        result, _ = multi_search(
            config,
            run_date=datetime(2026, 3, 30),
            preindex_journals=["jama"],
        )

        assert len(result) == 4
        # Primary MeSH, topic MeSH, primary preindex, topic preindex
        assert result[2].preindex is True
        assert result[2].source_topic == "primary"
        assert result[3].preindex is True
        assert result[3].source_topic == "af"

    @patch("src.search.pubmed_query.search")
    def test_no_preindex_when_journals_empty(self, mock_search):
        """No preindex searches run when preindex_journals is None or empty."""
        mock_search.return_value = ([_make_record("1001")], 1)

        config = SearchConfig(mesh_terms=["stroke"])
        result, _ = multi_search(config, run_date=datetime(2026, 3, 30))

        assert len(result) == 1
        mock_search.assert_called_once()

    @patch("src.search.pubmed_query._execute_query")
    @patch("src.search.pubmed_query.search")
    def test_preindex_dedup_across_topics(self, mock_search, mock_execute):
        """Preindex hit already found by topic MeSH is deduplicated."""
        mock_search.side_effect = [
            ([_make_record("1001")], 1),  # primary
            ([_make_record("2001")], 1),  # topic
        ]
        # Preindex for primary finds 2001 (already seen from topic MeSH)
        mock_execute.side_effect = [
            ([_make_record("2001")], 1),  # preindex primary — dup
            ([_make_record("3001")], 1),  # preindex topic — new
        ]

        config = SearchConfig(
            mesh_terms=["stroke"],
            topics=[Topic(name="af", mesh_terms=["atrial fibrillation"])],
        )
        result, _ = multi_search(
            config,
            run_date=datetime(2026, 3, 30),
            preindex_journals=["jama"],
        )

        assert len(result) == 3
        pmids = [r.pmid for r in result]
        assert pmids == ["1001", "2001", "3001"]
        assert result[1].preindex is False  # 2001 from MeSH, not preindex


class TestMultiSearchConfigLoading:
    """Verify topics round-trip through config loading."""

    def test_stroke_config_loads_topics(self):
        from src.config import load_search_config
        config = load_search_config(domain="stroke")
        assert len(config.topics) >= 1
        assert all(isinstance(t, Topic) for t in config.topics)
        assert all(t.name for t in config.topics)
        assert all(t.mesh_terms for t in config.topics)

    def test_legacy_config_has_no_topics(self):
        from src.config import load_search_config
        config = load_search_config()
        assert config.topics == []
