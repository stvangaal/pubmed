# owner: wp-pages
"""Tests for WordPress page sync."""

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.distribute.wp_pages import (
    compute_content_sha,
    parse_page_file,
    render_markdown_to_html,
    resolve_page_path,
    sync_pages,
)
from src.models import WordPressConfig


# --- Content resolution tests ---


class TestResolvePagePath:
    def test_domain_override_takes_precedence(self, tmp_path):
        """Domain-specific file wins over _defaults."""
        defaults = tmp_path / "_defaults"
        defaults.mkdir()
        (defaults / "about.md").write_text("default about")

        domain = tmp_path / "stroke"
        domain.mkdir()
        (domain / "about.md").write_text("stroke about")

        with patch("src.distribute.wp_pages.CONTENT_DIR", tmp_path):
            result = resolve_page_path("about", "stroke")
        assert result == domain / "about.md"

    def test_default_fallback(self, tmp_path):
        """Falls back to _defaults when domain file doesn't exist."""
        defaults = tmp_path / "_defaults"
        defaults.mkdir()
        (defaults / "privacy-policy.md").write_text("default privacy")

        domain = tmp_path / "stroke"
        domain.mkdir()
        # No privacy-policy.md in stroke/

        with patch("src.distribute.wp_pages.CONTENT_DIR", tmp_path):
            result = resolve_page_path("privacy-policy", "stroke")
        assert result == defaults / "privacy-policy.md"

    def test_missing_returns_none(self, tmp_path):
        """Returns None when no file exists for the slug."""
        defaults = tmp_path / "_defaults"
        defaults.mkdir()

        with patch("src.distribute.wp_pages.CONTENT_DIR", tmp_path):
            result = resolve_page_path("nonexistent", "stroke")
        assert result is None


class TestParsePageFile:
    def test_parses_frontmatter_and_body(self, tmp_path):
        page = tmp_path / "test.md"
        page.write_text(
            "---\nslug: test-page\ntitle: Test Page\nstatus: publish\n---\n\n# Hello\n\nBody text."
        )
        fm, body = parse_page_file(page)
        assert fm["slug"] == "test-page"
        assert fm["title"] == "Test Page"
        assert fm["status"] == "publish"
        assert "# Hello" in body
        assert "Body text." in body

    def test_handles_no_frontmatter(self, tmp_path):
        page = tmp_path / "test.md"
        page.write_text("# Just Markdown\n\nNo frontmatter here.")
        fm, body = parse_page_file(page)
        assert fm == {}
        assert "Just Markdown" in body

    def test_handles_menu_order(self, tmp_path):
        page = tmp_path / "test.md"
        page.write_text("---\nslug: x\nmenu_order: 10\n---\nBody")
        fm, _ = parse_page_file(page)
        assert fm["menu_order"] == 10


class TestRenderMarkdownToHtml:
    def test_wraps_in_wp_html_block(self):
        html = render_markdown_to_html("# Title\n\nParagraph.")
        assert html.startswith("<!-- wp:html -->")
        assert html.endswith("<!-- /wp:html -->")

    def test_renders_heading(self):
        html = render_markdown_to_html("# Title")
        assert "<h1>Title</h1>" in html

    def test_renders_paragraph(self):
        html = render_markdown_to_html("Hello world.")
        assert "<p>Hello world.</p>" in html

    def test_renders_list(self):
        html = render_markdown_to_html("- item one\n- item two")
        assert "<li>" in html
        assert "item one" in html

    def test_renders_bold(self):
        html = render_markdown_to_html("**bold text**")
        assert "<strong>bold text</strong>" in html


class TestComputeContentSha:
    def test_returns_sha256_hex(self, tmp_path):
        page = tmp_path / "test.md"
        content = b"test content"
        page.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest()
        assert compute_content_sha(page) == expected


# --- Sync tests ---


class TestSyncPages:
    def _make_config(self, **overrides):
        defaults = dict(
            enabled=True,
            site_url="https://example.com",
            clinical_topics_taxonomy="clinical_topics",
            pages=["landing", "about"],
        )
        defaults.update(overrides)
        return WordPressConfig(**defaults)

    def test_skips_when_disabled(self):
        config = self._make_config(enabled=False)
        result = sync_pages("stroke", config)
        assert result == {}

    def test_skips_when_no_site_url(self):
        config = self._make_config(site_url="")
        result = sync_pages("stroke", config)
        assert result == {}

    def test_skips_when_no_pages(self):
        config = self._make_config(pages=[])
        result = sync_pages("stroke", config)
        assert result == {}

    def test_skips_when_no_credentials(self):
        config = self._make_config()
        with patch.dict("os.environ", {}, clear=True):
            result = sync_pages("stroke", config)
        assert result == {}

    def test_dry_run_no_api_calls(self, tmp_path):
        """Dry run resolves and renders but makes no HTTP calls."""
        defaults = tmp_path / "_defaults"
        defaults.mkdir()
        (defaults / "landing.md").write_text(
            "---\nslug: landing\ntitle: Welcome\n---\n# Hello"
        )
        (defaults / "about.md").write_text(
            "---\nslug: about\ntitle: About\n---\n# About Us"
        )

        config = self._make_config()

        with patch("src.distribute.wp_pages.CONTENT_DIR", tmp_path), \
             patch("src.distribute.wp_pages.load_state", return_value={}), \
             patch("src.distribute.wp_pages.save_state") as mock_save, \
             patch("src.distribute.wp_pages.httpx") as mock_httpx, \
             patch.dict("os.environ", {"WP_USERNAME": "u", "WP_APP_PASSWORD": "p"}):
            result = sync_pages("stroke", config, dry_run=True)

        mock_httpx.get.assert_not_called()
        mock_httpx.post.assert_not_called()
        mock_save.assert_not_called()
        assert result == {}

    def test_sha_unchanged_skips_sync(self, tmp_path):
        """When content SHA matches state, skip the API call."""
        defaults = tmp_path / "_defaults"
        defaults.mkdir()
        page_file = defaults / "landing.md"
        page_file.write_text("---\nslug: landing\ntitle: Welcome\n---\n# Hello")
        sha = hashlib.sha256(page_file.read_bytes()).hexdigest()

        config = self._make_config(pages=["landing"])
        state = {"landing": {"wp_page_id": 42, "content_sha": sha, "last_synced": "2026-04-01T00:00:00Z"}}

        with patch("src.distribute.wp_pages.CONTENT_DIR", tmp_path), \
             patch("src.distribute.wp_pages.load_state", return_value=state), \
             patch("src.distribute.wp_pages.save_state"), \
             patch("src.distribute.wp_pages.httpx") as mock_httpx, \
             patch.dict("os.environ", {"WP_USERNAME": "u", "WP_APP_PASSWORD": "p"}):
            result = sync_pages("stroke", config)

        mock_httpx.get.assert_not_called()
        mock_httpx.post.assert_not_called()
        assert result == {"landing": 42}

    @patch("src.distribute.wp_pages.httpx")
    def test_creates_new_page(self, mock_httpx, tmp_path):
        """Creates a new page when slug doesn't exist in WordPress."""
        defaults = tmp_path / "_defaults"
        defaults.mkdir()
        (defaults / "about.md").write_text(
            "---\nslug: about\ntitle: About Us\nstatus: publish\nmenu_order: 20\n---\n# About"
        )

        # No existing page
        get_response = MagicMock()
        get_response.json.return_value = []
        get_response.raise_for_status = MagicMock()

        # Successful creation
        post_response = MagicMock()
        post_response.json.return_value = {"id": 99}
        post_response.raise_for_status = MagicMock()

        mock_httpx.get.return_value = get_response
        mock_httpx.post.return_value = post_response

        config = self._make_config(pages=["about"])

        with patch("src.distribute.wp_pages.CONTENT_DIR", tmp_path), \
             patch("src.distribute.wp_pages.load_state", return_value={}), \
             patch("src.distribute.wp_pages.save_state"), \
             patch.dict("os.environ", {"WP_USERNAME": "u", "WP_APP_PASSWORD": "p"}):
            result = sync_pages("stroke", config)

        assert result == {"about": 99}

    @patch("src.distribute.wp_pages.httpx")
    def test_updates_existing_page(self, mock_httpx, tmp_path):
        """Updates a page when it already exists in WordPress (found by slug)."""
        defaults = tmp_path / "_defaults"
        defaults.mkdir()
        (defaults / "about.md").write_text(
            "---\nslug: about\ntitle: About Us\n---\n# Updated About"
        )

        # Existing page found by slug
        get_response = MagicMock()
        get_response.json.return_value = [{"id": 55, "modified": "2026-03-01T00:00:00"}]
        get_response.raise_for_status = MagicMock()

        # Successful update
        post_response = MagicMock()
        post_response.json.return_value = {"id": 55}
        post_response.raise_for_status = MagicMock()

        mock_httpx.get.return_value = get_response
        mock_httpx.post.return_value = post_response

        config = self._make_config(pages=["about"])

        with patch("src.distribute.wp_pages.CONTENT_DIR", tmp_path), \
             patch("src.distribute.wp_pages.load_state", return_value={}), \
             patch("src.distribute.wp_pages.save_state"), \
             patch.dict("os.environ", {"WP_USERNAME": "u", "WP_APP_PASSWORD": "p"}):
            result = sync_pages("stroke", config)

        assert result == {"about": 55}

    @patch("src.distribute.wp_pages.httpx")
    def test_sets_front_page_for_landing(self, mock_httpx, tmp_path):
        """After syncing landing page, sets it as WordPress front page."""
        defaults = tmp_path / "_defaults"
        defaults.mkdir()
        (defaults / "landing.md").write_text(
            "---\nslug: landing\ntitle: Welcome\n---\n# Welcome"
        )

        # No existing page
        get_response = MagicMock()
        get_response.json.return_value = []
        get_response.raise_for_status = MagicMock()

        # Create page returns id 10
        post_response = MagicMock()
        post_response.json.return_value = {"id": 10}
        post_response.raise_for_status = MagicMock()

        # Settings update response
        settings_response = MagicMock()
        settings_response.raise_for_status = MagicMock()

        mock_httpx.get.return_value = get_response
        mock_httpx.post.return_value = post_response

        config = self._make_config(pages=["landing"])

        with patch("src.distribute.wp_pages.CONTENT_DIR", tmp_path), \
             patch("src.distribute.wp_pages.load_state", return_value={}), \
             patch("src.distribute.wp_pages.save_state"), \
             patch.dict("os.environ", {"WP_USERNAME": "u", "WP_APP_PASSWORD": "p"}):
            result = sync_pages("stroke", config)

        assert result == {"landing": 10}
        # Verify settings API was called (one of the post calls should be to /settings)
        settings_calls = [
            c for c in mock_httpx.post.call_args_list
            if "settings" in str(c)
        ]
        assert len(settings_calls) > 0

    def test_missing_slug_warns_and_continues(self, tmp_path):
        """Missing content file for a slug logs warning, continues to next."""
        defaults = tmp_path / "_defaults"
        defaults.mkdir()
        (defaults / "about.md").write_text(
            "---\nslug: about\ntitle: About\n---\n# About"
        )
        # "nonexistent" has no file

        get_response = MagicMock()
        get_response.json.return_value = []
        get_response.raise_for_status = MagicMock()

        post_response = MagicMock()
        post_response.json.return_value = {"id": 77}
        post_response.raise_for_status = MagicMock()

        config = self._make_config(pages=["nonexistent", "about"])

        with patch("src.distribute.wp_pages.CONTENT_DIR", tmp_path), \
             patch("src.distribute.wp_pages.load_state", return_value={}), \
             patch("src.distribute.wp_pages.save_state"), \
             patch("src.distribute.wp_pages.httpx") as mock_httpx, \
             patch.dict("os.environ", {"WP_USERNAME": "u", "WP_APP_PASSWORD": "p"}):
            mock_httpx.get.return_value = get_response
            mock_httpx.post.return_value = post_response
            result = sync_pages("stroke", config)

        # "about" should still be synced despite "nonexistent" failing
        assert "about" in result


# --- Contract tests ---


class TestWpConfigPagesField:
    def test_config_with_pages_list(self):
        """WordPressConfig accepts a pages list."""
        config = WordPressConfig(
            enabled=True,
            site_url="https://example.com",
            pages=["landing", "about", "privacy-policy"],
        )
        assert config.pages == ["landing", "about", "privacy-policy"]

    def test_config_default_empty_pages(self):
        """WordPressConfig defaults to empty pages list."""
        config = WordPressConfig()
        assert config.pages == []
