# owner: llm-summarize
"""Tests for parse_summary: multi-tag extraction and structured field parsing."""

from src.summarize.parse_summary import parse_summary, _extract_tags, _match_tag

SUBDOMAIN_OPTIONS = [
    "Acute Treatment",
    "Prevention",
    "Rehabilitation",
    "Hospital Care",
    "Imaging",
    "Epidemiology",
]


class TestExtractTags:
    def test_single_tag_new_format(self):
        lines = ["**Tags:** Acute Treatment", "Some citation line"]
        assert _extract_tags(lines, SUBDOMAIN_OPTIONS) == ["Acute Treatment"]

    def test_multi_tag_new_format(self):
        lines = ["**Tags:** Acute Treatment, Prevention", "Some citation line"]
        assert _extract_tags(lines, SUBDOMAIN_OPTIONS) == ["Acute Treatment", "Prevention"]

    def test_legacy_single_subdomain_format(self):
        lines = ["**Acute Treatment**", "Some citation line"]
        assert _extract_tags(lines, SUBDOMAIN_OPTIONS) == ["Acute Treatment"]

    def test_invalid_tag_filtered_out(self):
        lines = ["**Tags:** Acute Treatment, InvalidTag", "Citation"]
        result = _extract_tags(lines, SUBDOMAIN_OPTIONS)
        assert result == ["Acute Treatment"]

    def test_all_invalid_returns_none(self):
        lines = ["**Tags:** NotATag, AlsoNotATag", "Citation"]
        assert _extract_tags(lines, SUBDOMAIN_OPTIONS) is None

    def test_case_insensitive_match(self):
        lines = ["**Tags:** acute treatment, prevention", "Citation"]
        result = _extract_tags(lines, SUBDOMAIN_OPTIONS)
        assert result == ["Acute Treatment", "Prevention"]

    def test_skips_empty_lines(self):
        lines = ["", "  ", "**Tags:** Imaging", "Citation"]
        assert _extract_tags(lines, SUBDOMAIN_OPTIONS) == ["Imaging"]

    def test_empty_lines_only_returns_none(self):
        lines = ["", "  "]
        assert _extract_tags(lines, SUBDOMAIN_OPTIONS) is None

    def test_preserves_tag_order(self):
        lines = ["**Tags:** Prevention, Acute Treatment, Imaging"]
        result = _extract_tags(lines, SUBDOMAIN_OPTIONS)
        assert result == ["Prevention", "Acute Treatment", "Imaging"]

    def test_whitespace_around_tags(self):
        lines = ["**Tags:**   Acute Treatment ,  Prevention  "]
        result = _extract_tags(lines, SUBDOMAIN_OPTIONS)
        assert result == ["Acute Treatment", "Prevention"]


class TestMatchTag:
    def test_exact_match(self):
        assert _match_tag("Acute Treatment", SUBDOMAIN_OPTIONS) == "Acute Treatment"

    def test_case_insensitive(self):
        assert _match_tag("acute treatment", SUBDOMAIN_OPTIONS) == "Acute Treatment"

    def test_no_match(self):
        assert _match_tag("Nonexistent", SUBDOMAIN_OPTIONS) is None


class TestParseSummary:
    VALID_RESPONSE = (
        "**Tags:** Acute Treatment, Prevention\n"
        "Test Article. *Test Journal*. [12345](https://pubmed.ncbi.nlm.nih.gov/12345/)\n"
        "\n"
        "**Research Question:** Does X improve Y?\n"
        "\n"
        "X significantly improves Y in patients with Z.\n"
        "\n"
        "**Details:**\n"
        "- Design: RCT, N=100, adults\n"
        "- Primary outcome: 50% reduction (p<0.01)\n"
        "- Limitations: Single-center study\n"
        "\n"
        "**Short Summary:** X improves Y. This changes practice.\n"
    )

    LEGACY_RESPONSE = (
        "**Acute Treatment**\n"
        "Test Article. *Test Journal*. [12345](https://pubmed.ncbi.nlm.nih.gov/12345/)\n"
        "\n"
        "**Research Question:** Does X improve Y?\n"
        "\n"
        "X significantly improves Y in patients with Z.\n"
        "\n"
        "**Details:**\n"
        "- Design: RCT, N=100, adults\n"
        "- Primary outcome: 50% reduction (p<0.01)\n"
        "- Limitations: Single-center study\n"
        "\n"
        "**Short Summary:** X improves Y. This changes practice.\n"
    )

    def test_parses_multi_tag_response(self):
        result = parse_summary(self.VALID_RESPONSE, SUBDOMAIN_OPTIONS)
        assert result is not None
        assert result["tags"] == ["Acute Treatment", "Prevention"]
        assert result["citation"].startswith("Test Article")
        assert result["research_question"] == "Does X improve Y?"
        assert result["design"] == "RCT, N=100, adults"

    def test_parses_legacy_single_subdomain_response(self):
        result = parse_summary(self.LEGACY_RESPONSE, SUBDOMAIN_OPTIONS)
        assert result is not None
        assert result["tags"] == ["Acute Treatment"]

    def test_returns_none_for_invalid_tags(self):
        bad_response = self.VALID_RESPONSE.replace(
            "Acute Treatment, Prevention", "NotATag"
        )
        result = parse_summary(bad_response, SUBDOMAIN_OPTIONS)
        assert result is None

    def test_returns_none_for_missing_research_question(self):
        bad_response = self.VALID_RESPONSE.replace("**Research Question:**", "")
        result = parse_summary(bad_response, SUBDOMAIN_OPTIONS)
        assert result is None
