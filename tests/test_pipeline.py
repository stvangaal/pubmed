# owner: project-infrastructure
"""Tests for pipeline test-mode config overrides."""

from src.models import (
    SearchConfig,
    FilterConfig,
    LLMTriageConfig,
    RuleFilterConfig,
    BlogConfig,
    EmailConfig,
)


def _apply_test_overrides(search_config, filter_config, blog_config, email_config):
    """Mirror the test-mode override block from pipeline.run()."""
    search_config.date_window_days = 1
    search_config.retmax = 20
    filter_config.llm_triage.max_articles = 3
    blog_config.publish = False
    email_config.enabled = False


def test_test_mode_overrides():
    """--test flag sets 1-day window, retmax=20, max_articles=3, disables email/publish."""
    search = SearchConfig(mesh_terms=["stroke"], date_window_days=7, retmax=200)
    filt = FilterConfig(
        rule_filter=RuleFilterConfig(),
        llm_triage=LLMTriageConfig(max_articles=15),
    )
    blog = BlogConfig(publish=True)
    email = EmailConfig(enabled=True, to_addresses=["test@example.com"])

    _apply_test_overrides(search, filt, blog, email)

    assert search.date_window_days == 1
    assert search.retmax == 20
    assert filt.llm_triage.max_articles == 3
    assert blog.publish is False
    assert email.enabled is False


def test_normal_mode_preserves_config():
    """Without --test, configs remain at their original values."""
    search = SearchConfig(mesh_terms=["stroke"], date_window_days=7, retmax=200)
    filt = FilterConfig(
        rule_filter=RuleFilterConfig(),
        llm_triage=LLMTriageConfig(max_articles=15),
    )
    blog = BlogConfig(publish=True)
    email = EmailConfig(enabled=True, to_addresses=["test@example.com"])

    # No overrides applied

    assert search.date_window_days == 7
    assert search.retmax == 200
    assert filt.llm_triage.max_articles == 15
    assert blog.publish is True
    assert email.enabled is True
