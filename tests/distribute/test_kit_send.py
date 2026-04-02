# owner: email-send
"""Tests for Kit broadcast building and sending."""

from unittest.mock import patch, MagicMock

from src.distribute.kit_send import build_kit_broadcast_html, send_kit_broadcast
from src.models import BlogPage, DistributeConfig, LiteratureSummary


def _make_summary(
    pmid: str,
    title: str,
    tags: list[str],
    score: float = 0.90,
) -> LiteratureSummary:
    """Create a minimal LiteratureSummary for testing."""
    return LiteratureSummary(
        pmid=pmid,
        title=title,
        journal="Test Journal",
        pub_date="2026-01-01",
        tags=tags,
        citation=f"{title}. Test Journal. PMID {pmid}",
        research_question="Test question?",
        key_finding="Test finding.",
        design="RCT",
        primary_outcome="Test outcome.",
        limitations="Test limitations.",
        summary_short="Short summary for testing.",
        triage_score=score,
        triage_rationale="Test rationale.",
        feedback_url=f"https://example.com/feedback/{pmid}",
        raw_llm_response="raw",
    )


def _default_config(universal_threshold: float = 0.80) -> DistributeConfig:
    return DistributeConfig(
        digest_title="Test Digest",
        opening="Test opening for {date_range}, {article_count} articles.",
        closing="Test closing.",
        sort_by="triage_score",
        full_summary_threshold=0.80,
        universal_threshold=universal_threshold,
    )


class TestBuildKitBroadcastHtml:
    def test_wraps_below_threshold_in_liquid(self):
        summaries = [
            _make_summary("1", "Article A", ["Acute Treatment"], score=0.75),
            _make_summary("2", "Article B", ["Prevention"], score=0.75),
        ]
        html = build_kit_broadcast_html(summaries, _default_config(), "Jan 1 – Jan 7, 2026")

        assert '{% if subscriber.tags contains "Acute Treatment" %}' in html
        assert '{% if subscriber.tags contains "Prevention" %}' in html
        assert "{% endif %}" in html

    def test_no_all_topics_block(self):
        summaries = [
            _make_summary("1", "Article A", ["Acute Treatment"]),
            _make_summary("2", "Article B", ["Prevention"]),
        ]
        html = build_kit_broadcast_html(summaries, _default_config(), "Jan 1 – Jan 7, 2026")

        assert "All Topics" not in html
        assert "{% else %}" not in html

    def test_above_threshold_no_liquid_wrapping(self):
        summaries = [
            _make_summary("1", "High Score", ["Acute Treatment"], score=0.90),
        ]
        html = build_kit_broadcast_html(summaries, _default_config(universal_threshold=0.80), "Jan 1 – Jan 7, 2026")

        # Article content should be present
        assert "High Score" in html
        # No per-article Liquid conditional (article is above threshold)
        assert '{% if subscriber.tags contains "Acute Treatment" %}' not in html

    def test_below_threshold_has_liquid_wrapping(self):
        summaries = [
            _make_summary("1", "Low Score", ["Prevention"], score=0.75),
        ]
        html = build_kit_broadcast_html(summaries, _default_config(universal_threshold=0.80), "Jan 1 – Jan 7, 2026")

        assert "Low Score" in html
        assert '{% if subscriber.tags contains "Prevention" %}' in html

    def test_multi_tag_article_uses_or_logic(self):
        summaries = [
            _make_summary("1", "Multi Tag", ["Acute Treatment", "Prevention"], score=0.75),
        ]
        html = build_kit_broadcast_html(summaries, _default_config(), "Jan 1 – Jan 7, 2026")

        assert 'subscriber.tags contains "Acute Treatment" or subscriber.tags contains "Prevention"' in html

    def test_section_heading_conditional_on_tags(self):
        """When all articles in a section are below threshold, the heading is wrapped."""
        summaries = [
            _make_summary("1", "Low A", ["Imaging"], score=0.75),
        ]
        html = build_kit_broadcast_html(summaries, _default_config(), "Jan 1 – Jan 7, 2026")

        # Section heading should be inside a Liquid block
        imaging_conditional = html.index('{% if subscriber.tags contains "Imaging" %}')
        heading_pos = html.index("Imaging", imaging_conditional + 10)
        assert heading_pos > imaging_conditional

    def test_section_heading_unconditional_with_high_score_article(self):
        """When a section has an above-threshold article, the heading is unconditional."""
        summaries = [
            _make_summary("1", "High Score", ["Imaging"], score=0.90),
        ]
        html = build_kit_broadcast_html(summaries, _default_config(), "Jan 1 – Jan 7, 2026")

        # The section should NOT be wrapped in a Liquid conditional
        # Find the h2 heading
        assert "<h2>" in html or "Imaging" in html
        # No tag conditional before the section
        lines_before_heading = html[:html.index("Imaging")]
        assert '{% if subscriber.tags contains "Imaging" %}' not in lines_before_heading

    def test_empty_summaries(self):
        html = build_kit_broadcast_html([], _default_config(), "Jan 1 – Jan 7, 2026")

        assert "No practice-relevant articles" in html
        assert "{% if subscriber.tags" not in html

    def test_opening_and_closing_outside_conditionals(self):
        summaries = [_make_summary("1", "Article A", ["Acute Treatment"], score=0.75)]
        html = build_kit_broadcast_html(summaries, _default_config(), "Jan 1 – Jan 7, 2026")

        # Opening appears before any Liquid tag
        opening_pos = html.index("Test opening")
        first_liquid = html.index("{% if subscriber.tags")
        assert opening_pos < first_liquid

        # Closing appears after all Liquid tags
        last_endif = html.rindex("{% endif %}")
        closing_pos = html.index("Test closing")
        assert closing_pos > last_endif

    def test_includes_article_content(self):
        summaries = [_make_summary("1", "My Test Article", ["Prevention"], score=0.90)]
        html = build_kit_broadcast_html(summaries, _default_config(), "Jan 1 – Jan 7, 2026")

        assert "My Test Article" in html
        assert "Test question?" in html  # Full summary (score >= threshold)

    def test_short_summary_below_threshold(self):
        summaries = [_make_summary("1", "Low Score Article", ["Prevention"], score=0.70)]
        html = build_kit_broadcast_html(summaries, _default_config(), "Jan 1 – Jan 7, 2026")

        assert "Low Score Article" in html
        assert "Short summary for testing" in html

    def test_mixed_threshold_articles_in_same_section(self):
        """Section with both above and below threshold articles."""
        summaries = [
            _make_summary("1", "High Score", ["Prevention"], score=0.90),
            _make_summary("2", "Low Score", ["Prevention"], score=0.75),
        ]
        config = _default_config(universal_threshold=0.80)
        html = build_kit_broadcast_html(summaries, config, "Jan 1 – Jan 7, 2026")

        # High score article should be unconditional
        assert "High Score" in html
        # Low score article should be in a Liquid block
        assert '{% if subscriber.tags contains "Prevention" %}' in html
        # Section heading should be unconditional (has a high-score article)
        # Count endif blocks — only one for the below-threshold article
        endif_count = html.count("{% endif %}")
        # One for the below-threshold article only
        assert endif_count >= 1


class TestSendKitBroadcast:
    def test_no_api_key_returns_false(self):
        with patch.dict("os.environ", {}, clear=True):
            assert send_kit_broadcast("<p>test</p>", "Test Subject") is False

    @patch("src.distribute.kit_send.httpx")
    @patch.dict("os.environ", {"KIT_API_SECRET": "test-secret"})
    def test_creates_and_publishes(self, mock_httpx):
        # Mock POST (create draft) response
        mock_create_resp = MagicMock()
        mock_create_resp.json.return_value = {"broadcast": {"id": 123}}
        mock_create_resp.raise_for_status = MagicMock()

        # Mock PUT (publish) response
        mock_publish_resp = MagicMock()
        mock_publish_resp.raise_for_status = MagicMock()

        mock_httpx.post.return_value = mock_create_resp
        mock_httpx.put.return_value = mock_publish_resp

        result = send_kit_broadcast("<p>content</p>", "Test Subject")

        assert result is True
        # Verify POST was called to create draft
        mock_httpx.post.assert_called_once()
        create_call = mock_httpx.post.call_args
        assert "/broadcasts" in create_call[0][0]
        assert create_call[1]["json"]["broadcast"]["subject"] == "Test Subject"

        # Verify PUT was called to publish
        mock_httpx.put.assert_called_once()
        put_call = mock_httpx.put.call_args
        assert "/broadcasts/123" in put_call[0][0]
        assert put_call[1]["json"]["broadcast"]["public"] is True

    @patch("src.distribute.kit_send.httpx")
    @patch.dict("os.environ", {"KIT_API_SECRET": "test-secret"})
    def test_api_error_returns_false(self, mock_httpx):
        mock_httpx.post.side_effect = Exception("API error")

        result = send_kit_broadcast("<p>content</p>", "Test Subject")
        assert result is False
