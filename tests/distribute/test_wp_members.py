# owner: wp-publish
"""Tests for WordPress member preference querying."""

from unittest.mock import MagicMock, patch

from src.distribute.wp_members import Member, fetch_members


class TestFetchMembers:
    @patch("src.distribute.wp_members.httpx")
    def test_fetches_members(self, mock_httpx):
        response = MagicMock()
        response.json.return_value = [
            {
                "email": "alice@example.com",
                "display_name": "Alice",
                "topics": ["Acute Treatment", "Prevention"],
            },
            {
                "email": "bob@example.com",
                "display_name": "Bob",
                "topics": ["Rehabilitation"],
            },
        ]
        response.raise_for_status = MagicMock()
        mock_httpx.get.return_value = response

        members = fetch_members("https://example.com")

        assert len(members) == 2
        assert members[0].email == "alice@example.com"
        assert members[0].topics == ["Acute Treatment", "Prevention"]
        assert members[1].display_name == "Bob"

    @patch("src.distribute.wp_members.httpx")
    def test_skips_entries_without_email(self, mock_httpx):
        response = MagicMock()
        response.json.return_value = [
            {"email": "", "display_name": "No Email"},
            {"email": "valid@example.com", "topics": []},
        ]
        response.raise_for_status = MagicMock()
        mock_httpx.get.return_value = response

        members = fetch_members("https://example.com")

        assert len(members) == 1
        assert members[0].email == "valid@example.com"

    @patch("src.distribute.wp_members.httpx")
    def test_returns_empty_on_failure(self, mock_httpx):
        mock_httpx.get.side_effect = Exception("Connection failed")

        members = fetch_members("https://example.com")
        assert members == []

    @patch("src.distribute.wp_members.httpx")
    def test_sends_api_secret_header(self, mock_httpx):
        response = MagicMock()
        response.json.return_value = []
        response.raise_for_status = MagicMock()
        mock_httpx.get.return_value = response

        fetch_members("https://example.com", api_secret="my-secret")

        call_kwargs = mock_httpx.get.call_args
        assert call_kwargs.kwargs["headers"]["X-Digest-Secret"] == "my-secret"
