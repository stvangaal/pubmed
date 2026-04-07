# owner: wp-publish
"""Tests for WordPress article publishing."""

import base64
from unittest.mock import MagicMock, patch

import pytest

from src.distribute.wp_publish import (
    _build_auth_header,
    _render_article_html,
    publish_to_wordpress,
)
from src.models import LiteratureSummary, WordPressConfig


def _make_summary(**overrides) -> LiteratureSummary:
    defaults = dict(
        pmid="12345678",
        title="Test Article",
        journal="Test Journal",
        pub_date="2026-01-01",
        tags=["Acute Treatment"],
        citation="Author et al. Test Journal. 2026.",
        research_question="Does X improve Y?",
        key_finding="X improves Y significantly.",
        design="RCT, N=200, adults with condition Z",
        primary_outcome="50% improvement (p<0.001)",
        limitations="Single center study",
        summary_short="X improves Y in adults with Z.",
        triage_score=0.85,
        triage_rationale="Highly relevant",
        feedback_url="https://forms.example.com?pmid=12345678",
        raw_llm_response="raw response",
    )
    defaults.update(overrides)
    return LiteratureSummary(**defaults)


class TestBuildAuthHeader:
    def test_basic_auth_encoding(self):
        header = _build_auth_header("user", "pass")
        expected = base64.b64encode(b"user:pass").decode()
        assert header == f"Basic {expected}"


class TestRenderArticleHtml:
    def test_contains_all_sections(self):
        summary = _make_summary()
        html = _render_article_html(summary)
        assert "Research Question" in html
        assert "Key Finding" in html
        assert "Study Design" in html
        assert "Primary Outcome" in html
        assert "Limitations" in html
        assert summary.citation in html

    def test_includes_feedback_link(self):
        summary = _make_summary(feedback_url="https://example.com/feedback")
        html = _render_article_html(summary)
        assert "https://example.com/feedback" in html

    def test_no_feedback_link_when_empty(self):
        summary = _make_summary(feedback_url="")
        html = _render_article_html(summary)
        assert "Provide feedback" not in html


class TestPublishToWordpress:
    def test_skips_when_disabled(self):
        config = WordPressConfig(enabled=False, site_url="https://example.com")
        result = publish_to_wordpress([], config)
        assert result == {}

    def test_skips_when_no_site_url(self):
        config = WordPressConfig(enabled=True, site_url="")
        result = publish_to_wordpress([], config)
        assert result == {}

    def test_skips_when_no_credentials(self):
        config = WordPressConfig(enabled=True, site_url="https://example.com")
        with patch.dict("os.environ", {}, clear=True):
            result = publish_to_wordpress([_make_summary()], config)
        assert result == {}

    @patch("src.distribute.wp_publish.httpx")
    def test_creates_posts(self, mock_httpx):
        config = WordPressConfig(
            enabled=True,
            site_url="https://example.com",
            clinical_topics_taxonomy="clinical_topics",
        )

        # Mock taxonomy term fetch (existing terms)
        terms_response = MagicMock()
        terms_response.json.return_value = [
            {"id": 1, "name": "Acute Treatment"},
        ]
        terms_response.raise_for_status = MagicMock()

        # Mock post creation
        post_response = MagicMock()
        post_response.json.return_value = {"id": 42}
        post_response.raise_for_status = MagicMock()

        mock_httpx.get.return_value = terms_response
        mock_httpx.post.return_value = post_response

        summary = _make_summary(pmid="99999")

        with patch.dict("os.environ", {"WP_USERNAME": "admin", "WP_APP_PASSWORD": "secret"}):
            result = publish_to_wordpress([summary], config)

        assert result == {"99999": 42}

    @patch("src.distribute.wp_publish.httpx")
    def test_creates_posts_with_conditions(self, mock_httpx):
        """Verify posts include conditions taxonomy term when source_topic is a specific condition."""
        config = WordPressConfig(
            enabled=True,
            site_url="https://example.com",
            clinical_topics_taxonomy="clinical_topics",
            conditions_taxonomy="conditions",
        )

        # Track GET calls to return different responses per taxonomy
        def mock_get(url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if "conditions" in url and "taxonomies" not in url:
                resp.json.return_value = [{"id": 10, "name": "atrial-fibrillation"}]
            else:
                resp.json.return_value = [{"id": 1, "name": "Acute Treatment"}]
            return resp

        mock_httpx.get.side_effect = mock_get

        post_response = MagicMock()
        post_response.json.return_value = {"id": 42}
        post_response.raise_for_status = MagicMock()
        mock_httpx.post.return_value = post_response

        summary = _make_summary(
            pmid="99999",
            tags=["Acute Treatment"],
            source_topic="atrial-fibrillation",
        )

        with patch.dict("os.environ", {"WP_USERNAME": "admin", "WP_APP_PASSWORD": "secret"}):
            result = publish_to_wordpress([summary], config)

        assert result == {"99999": 42}
        # Verify the post creation call included conditions taxonomy
        post_calls = [c for c in mock_httpx.post.call_args_list if "/posts" in str(c)]
        assert len(post_calls) == 1
        post_data = post_calls[0].kwargs.get("json", post_calls[0][1].get("json", {})) if post_calls[0].kwargs else {}
        # The post data should include the conditions taxonomy key
        assert "conditions" in post_data

    @patch("src.distribute.wp_publish.httpx")
    def test_skips_conditions_for_primary(self, mock_httpx):
        """Verify no conditions term is attached when source_topic is 'primary'."""
        config = WordPressConfig(
            enabled=True,
            site_url="https://example.com",
            clinical_topics_taxonomy="clinical_topics",
            conditions_taxonomy="conditions",
        )

        terms_response = MagicMock()
        terms_response.json.return_value = [{"id": 1, "name": "Acute Treatment"}]
        terms_response.raise_for_status = MagicMock()

        # Conditions fetch returns empty (no conditions terms needed)
        conditions_response = MagicMock()
        conditions_response.json.return_value = []
        conditions_response.raise_for_status = MagicMock()

        def mock_get(url, **kwargs):
            if "conditions" in url and "taxonomies" not in url:
                return conditions_response
            return terms_response

        mock_httpx.get.side_effect = mock_get

        post_response = MagicMock()
        post_response.json.return_value = {"id": 42}
        post_response.raise_for_status = MagicMock()
        mock_httpx.post.return_value = post_response

        summary = _make_summary(pmid="99999", source_topic="primary")

        with patch.dict("os.environ", {"WP_USERNAME": "admin", "WP_APP_PASSWORD": "secret"}):
            result = publish_to_wordpress([summary], config)

        assert result == {"99999": 42}
        # Verify the post creation call did NOT include conditions taxonomy
        post_calls = [c for c in mock_httpx.post.call_args_list if "/posts" in str(c)]
        assert len(post_calls) == 1
        post_data = post_calls[0].kwargs.get("json", post_calls[0][1].get("json", {})) if post_calls[0].kwargs else {}
        assert "conditions" not in post_data
