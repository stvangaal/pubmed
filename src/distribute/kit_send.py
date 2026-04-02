# owner: email-send
"""Create and send Kit (ConvertKit) broadcasts with per-subscriber topic filtering.

Uses Liquid conditional blocks so each subscriber sees only the articles
matching their tags. Articles scoring above the universal threshold are
shown to all subscribers unconditionally. Section headings are wrapped
in Liquid conditionals to avoid empty sections for non-matching subscribers.
"""

import logging
import os
from collections import OrderedDict
from datetime import datetime, timezone

import httpx

from src.distribute.digest_build import (
    group_by_subdomain,
    is_narrative_review,
    render_full_markdown,
    render_short_markdown,
    sort_summaries,
    subdomain_label,
)
from src.distribute.email_send import markdown_to_html
from src.models import (
    BlogPage,
    DistributeConfig,
    LiteratureSummary,
    LLMUsage,
)

logger = logging.getLogger(__name__)

KIT_API_BASE = "https://api.kit.com/v4"


def _liquid_tag_condition(tags: list[str]) -> str:
    """Build a Liquid OR condition for a list of tags.

    Example: 'subscriber.tags contains "Acute Treatment" or subscriber.tags contains "Prevention"'
    """
    clauses = [f'subscriber.tags contains "{t}"' for t in tags]
    return " or ".join(clauses)


def _collect_section_tags(
    group: list[LiteratureSummary], universal_threshold: float
) -> list[str]:
    """Collect all unique tags from below-threshold articles in a section.

    Used to build the Liquid conditional for section headings — the heading
    should be visible if the subscriber matches any tag from any below-threshold
    article in the section, OR if any article is above threshold (unconditional).
    """
    has_universal = any(s.triage_score >= universal_threshold for s in group)
    if has_universal:
        return []  # Empty means unconditional — section always visible

    all_tags: list[str] = []
    seen: set[str] = set()
    for s in group:
        for t in s.tags:
            if t not in seen:
                all_tags.append(t)
                seen.add(t)
    return all_tags


def build_kit_broadcast_html(
    summaries: list[LiteratureSummary],
    config: DistributeConfig,
    date_range: str,
    blog_page: BlogPage | None = None,
    llm_usage: list[LLMUsage] | None = None,
) -> str:
    """Build HTML email content with Liquid conditionals for Kit broadcast.

    Articles scoring >= universal_threshold appear for all subscribers.
    Articles below the threshold are wrapped in per-article Liquid conditionals
    using OR logic across the article's tags. Section headings are wrapped
    to avoid empty sections for non-matching subscribers.

    Args:
        summaries: Article summaries from this pipeline run.
        config: DistributeConfig with sort/threshold settings.
        date_range: Human-readable date range string.
        blog_page: Optional BlogPage for article URLs.
        llm_usage: Optional LLM usage data (not included in Kit broadcast).

    Returns:
        HTML string with embedded Liquid conditional blocks.
    """
    article_count = len(summaries)
    opening = config.opening.format(
        date_range=date_range, article_count=article_count
    )

    # Opening is shown to everyone (no conditional)
    parts = [markdown_to_html(opening)]

    if not summaries:
        parts.append("<p>No practice-relevant articles identified this week.</p>")
    else:
        sorted_summaries = sort_summaries(summaries, config.sort_by)
        topic_groups = group_by_subdomain(sorted_summaries)

        parts.append(
            _render_topic_groups(topic_groups, config, blog_page)
        )

    # Closing is shown to everyone
    if config.closing:
        parts.append(markdown_to_html(config.closing))

    return "\n".join(parts)


def _render_topic_groups(
    topic_groups: OrderedDict[str, list[LiteratureSummary]],
    config: DistributeConfig,
    blog_page: BlogPage | None,
) -> str:
    """Render all topic groups as HTML with per-article Liquid conditionals.

    Section headings are conditionally wrapped so subscribers without matching
    tags don't see empty sections. Articles above the universal threshold
    are rendered unconditionally.
    """
    parts = []
    for topic_name, group in topic_groups.items():
        label = subdomain_label(topic_name)

        # Determine if this section heading needs a Liquid conditional
        section_tags = _collect_section_tags(group, config.universal_threshold)

        if section_tags:
            parts.append(f"{{% if {_liquid_tag_condition(section_tags)} %}}")

        parts.append(
            _render_section_html(group, config, blog_page, label)
        )

        if section_tags:
            parts.append("{% endif %}")

    return "\n".join(parts)


def _render_section_html(
    group: list[LiteratureSummary],
    config: DistributeConfig,
    blog_page: BlogPage | None,
    label: str,
) -> str:
    """Render a single section with per-article Liquid wrapping."""
    parts = [markdown_to_html(f"## {label}\n")]

    for s in group:
        is_full = (
            s.triage_score >= config.full_summary_threshold
            and not is_narrative_review(s)
        )
        if is_full:
            article_md = render_full_markdown(s)
        else:
            blog_url = (
                blog_page.article_urls.get(s.pmid) if blog_page else None
            )
            article_md = render_short_markdown(s, blog_url)

        article_html = markdown_to_html(article_md)

        if s.triage_score >= config.universal_threshold:
            parts.append(article_html)
        else:
            condition = _liquid_tag_condition(s.tags)
            parts.append(f"{{% if {condition} %}}")
            parts.append(article_html)
            parts.append("{% endif %}")

    return "\n".join(parts)


def send_kit_broadcast(html_content: str, subject: str) -> bool:
    """Create and publish a Kit broadcast.

    Two-step process:
    1. POST /v4/broadcasts — create draft
    2. PUT /v4/broadcasts/{id} — publish (send immediately)

    Requires KIT_API_SECRET environment variable.

    Returns:
        True if broadcast was created and published, False otherwise.
    """
    api_secret = os.environ.get("KIT_API_SECRET")
    if not api_secret:
        logger.warning("KIT_API_SECRET not set, skipping Kit broadcast")
        return False

    headers = {
        "Authorization": f"Bearer {api_secret}",
        "Content-Type": "application/json",
    }

    try:
        # Step 1: Create draft broadcast
        create_resp = httpx.post(
            f"{KIT_API_BASE}/broadcasts",
            json={
                "broadcast": {
                    "subject": subject,
                    "content": html_content,
                    "description": f"Pipeline digest — {subject}",
                }
            },
            headers=headers,
            timeout=30,
        )
        create_resp.raise_for_status()
        broadcast = create_resp.json().get("broadcast", create_resp.json())
        broadcast_id = broadcast["id"]
        logger.info("Kit broadcast draft created (id: %s)", broadcast_id)

        # Step 2: Publish the broadcast
        send_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        publish_resp = httpx.put(
            f"{KIT_API_BASE}/broadcasts/{broadcast_id}",
            json={
                "broadcast": {
                    "public": True,
                    "send_at": send_at,
                }
            },
            headers=headers,
            timeout=30,
        )
        publish_resp.raise_for_status()
        logger.info("Kit broadcast published (id: %s)", broadcast_id)
        return True

    except Exception:
        logger.warning("Failed to send Kit broadcast", exc_info=True)
        return False
