# owner: email-send
"""Create and send Kit (ConvertKit) broadcasts with per-subscriber topic filtering.

Uses Liquid conditional blocks so each subscriber sees only the subdomain
sections matching their tags. Subscribers with the "All Topics" tag receive
the full unfiltered digest.
"""

import logging
import os
from collections import OrderedDict
from datetime import datetime, timezone

import httpx

from src.distribute.digest_build import (
    _group_by_subdomain,
    _is_narrative_review,
    _render_full_markdown,
    _render_short_markdown,
    _sort_summaries,
    _subdomain_label,
)
from src.distribute.email_send import _markdown_to_html
from src.models import (
    BlogPage,
    DistributeConfig,
    LiteratureSummary,
    LLMUsage,
)

logger = logging.getLogger(__name__)

KIT_API_BASE = "https://api.kit.com/v4"


def build_kit_broadcast_html(
    summaries: list[LiteratureSummary],
    config: DistributeConfig,
    date_range: str,
    blog_page: BlogPage | None = None,
    llm_usage: list[LLMUsage] | None = None,
) -> str:
    """Build HTML email content with Liquid conditionals for Kit broadcast.

    Each subdomain section is wrapped in a Liquid tag check so Kit renders
    only the sections matching a subscriber's selected topics. Subscribers
    tagged "All Topics" get the full digest.

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
    parts = [_markdown_to_html(opening)]

    if not summaries:
        parts.append("<p>No practice-relevant articles identified this week.</p>")
    else:
        sorted_summaries = _sort_summaries(summaries, config.sort_by)
        topic_groups = _group_by_subdomain(sorted_summaries)

        # "All Topics" block — full digest, no filtering
        all_topics_html = _render_topic_groups(
            topic_groups, config, blog_page, wrap_liquid=False
        )
        parts.append('{% if subscriber.tags contains "All Topics" %}')
        parts.append(all_topics_html)
        parts.append("{% else %}")

        # Per-topic conditional blocks
        parts.append(
            _render_topic_groups(
                topic_groups, config, blog_page, wrap_liquid=True
            )
        )

        parts.append("{% endif %}")

    # Closing is shown to everyone
    if config.closing:
        parts.append(_markdown_to_html(config.closing))

    return "\n".join(parts)


def _render_topic_groups(
    topic_groups: OrderedDict[str, list[LiteratureSummary]],
    config: DistributeConfig,
    blog_page: BlogPage | None,
    wrap_liquid: bool,
) -> str:
    """Render all topic groups as HTML, optionally wrapped in Liquid conditionals."""
    parts = []
    for topic_name, group in topic_groups.items():
        label = _subdomain_label(topic_name)

        section_md_parts = [f"## {label}\n"]
        for s in group:
            is_full = (
                s.triage_score >= config.full_summary_threshold
                and not _is_narrative_review(s)
            )
            if is_full:
                section_md_parts.append(_render_full_markdown(s))
            else:
                blog_url = (
                    blog_page.article_urls.get(s.pmid) if blog_page else None
                )
                section_md_parts.append(_render_short_markdown(s, blog_url))

        section_html = _markdown_to_html("\n\n".join(section_md_parts))

        if wrap_liquid:
            parts.append(f'{{% if subscriber.tags contains "{label}" %}}')
            parts.append(section_html)
            parts.append("{% endif %}")
        else:
            parts.append(section_html)

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
