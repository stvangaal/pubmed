# owner: pubmed-query
"""Tests for multi_search — multiple independent queries with deduplication."""

from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from src.models import PubmedRecord, SearchConfig, SearchProfile
from src.search.pubmed_query import multi_search


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


class TestMultiSearchNoProfiles:
    """When search_profiles is empty, multi_search behaves like search."""

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


class TestMultiSearchWithProfiles:
    """When search_profiles are configured, results are merged and deduped."""

    @patch("src.search.pubmed_query.search")
    def test_merges_profile_results(self, mock_search):
        primary = [_make_record("1001")]
        profile_results = [_make_record("2001"), _make_record("2002")]
        mock_search.side_effect = [
            (primary, 1),
            (profile_results, 2),
        ]

        config = SearchConfig(
            mesh_terms=["stroke"],
            search_profiles=[
                SearchProfile(name="af", mesh_terms=["atrial fibrillation"]),
            ],
        )
        result, total = multi_search(config, run_date=datetime(2026, 3, 23))

        assert len(result) == 3
        assert total == 3
        assert [r.pmid for r in result] == ["1001", "2001", "2002"]

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
            search_profiles=[
                SearchProfile(name="af", mesh_terms=["atrial fibrillation"]),
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
            search_profiles=[
                SearchProfile(name="af", mesh_terms=["atrial fibrillation"]),
                SearchProfile(name="cs", mesh_terms=["carotid stenosis"]),
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
            search_profiles=[
                SearchProfile(name="af", mesh_terms=["atrial fibrillation"]),
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
        assert profile_config.search_profiles == []

    @patch("src.search.pubmed_query.search")
    def test_profile_additional_terms_passed(self, mock_search):
        mock_search.return_value = ([], 0)

        config = SearchConfig(
            mesh_terms=["stroke"],
            search_profiles=[
                SearchProfile(
                    name="af",
                    mesh_terms=["atrial fibrillation"],
                    additional_terms=["anticoagulant"],
                ),
            ],
        )
        multi_search(config)

        profile_config = mock_search.call_args_list[1][0][0]
        assert profile_config.additional_terms == ["anticoagulant"]


class TestMultiSearchConfigLoading:
    """Verify search_profiles round-trip through config loading."""

    def test_stroke_config_loads_profiles(self):
        from src.config import load_search_config
        config = load_search_config(domain="stroke")
        assert len(config.search_profiles) >= 1
        assert all(isinstance(p, SearchProfile) for p in config.search_profiles)
        assert all(p.name for p in config.search_profiles)
        assert all(p.mesh_terms for p in config.search_profiles)

    def test_legacy_config_has_no_profiles(self):
        from src.config import load_search_config
        config = load_search_config()
        assert config.search_profiles == []
