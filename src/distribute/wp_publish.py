# owner: wp-publish
"""Upload summarized articles as WordPress posts via the REST API.

Each LiteratureSummary becomes a WordPress post with:
- Title and rendered HTML content
- Clinical topic taxonomy terms (mapped from article tags)
- Custom meta fields (PMID, triage score, journal, pub date, etc.)

Authentication uses WordPress Application Passwords via environment
variables WP_USERNAME and WP_APP_PASSWORD.
"""

import base64
import logging
import os

import httpx

from src.models import LiteratureSummary, WordPressConfig

logger = logging.getLogger(__name__)


def publish_to_wordpress(
    summaries: list[LiteratureSummary],
    config: WordPressConfig,
) -> dict[str, int]:
    """Upload each summary as a WordPress post.

    Args:
        summaries: Article summaries to publish.
        config: WordPressConfig with site URL and taxonomy slug.

    Returns:
        Dict mapping PMID to WordPress post ID for successfully created posts.
    """
    if not config.enabled:
        logger.info("WordPress publishing disabled (enabled: false), skipping")
        return {}

    if not config.site_url:
        logger.warning("WordPress site_url not configured, skipping")
        return {}

    username = os.environ.get("WP_USERNAME")
    app_password = os.environ.get("WP_APP_PASSWORD")
    if not username or not app_password:
        logger.warning(
            "WP_USERNAME or WP_APP_PASSWORD not set, skipping WordPress publish"
        )
        return {}

    auth_header = _build_auth_header(username, app_password)
    api_base = f"{config.site_url.rstrip('/')}/wp-json/wp/v2"

    # Resolve taxonomy term IDs for all tags across summaries
    all_tags = set()
    for s in summaries:
        all_tags.update(s.tags)
    term_map = _resolve_taxonomy_terms(
        api_base, auth_header, config.clinical_topics_taxonomy, all_tags
    )

    created: dict[str, int] = {}
    for s in summaries:
        post_id = _create_post(s, api_base, auth_header, config, term_map)
        if post_id:
            created[s.pmid] = post_id

    logger.info("WordPress: published %d/%d articles", len(created), len(summaries))
    return created


def _build_auth_header(username: str, app_password: str) -> str:
    """Build HTTP Basic Auth header for WordPress Application Passwords."""
    credentials = f"{username}:{app_password}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def _resolve_taxonomy_terms(
    api_base: str,
    auth_header: str,
    taxonomy: str,
    tags: set[str],
) -> dict[str, int]:
    """Map tag names to WordPress taxonomy term IDs, creating terms as needed.

    Args:
        api_base: WordPress REST API base URL.
        auth_header: Authorization header value.
        taxonomy: Taxonomy slug (e.g., "clinical_topics").
        tags: Set of tag names to resolve.

    Returns:
        Dict mapping tag name to term ID.
    """
    headers = {"Authorization": auth_header}
    term_map: dict[str, int] = {}

    # Fetch existing terms
    try:
        resp = httpx.get(
            f"{api_base}/{taxonomy}",
            params={"per_page": 100},
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        for term in resp.json():
            term_map[term["name"]] = term["id"]
    except Exception:
        logger.warning("Failed to fetch existing %s terms", taxonomy, exc_info=True)

    # Create any missing terms
    for tag in tags:
        if tag in term_map:
            continue
        try:
            resp = httpx.post(
                f"{api_base}/{taxonomy}",
                json={"name": tag},
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            term_map[tag] = resp.json()["id"]
            logger.info("Created WordPress taxonomy term: %s (id: %d)", tag, term_map[tag])
        except Exception:
            logger.warning("Failed to create taxonomy term '%s'", tag, exc_info=True)

    return term_map


def _render_article_html(summary: LiteratureSummary) -> str:
    """Render a LiteratureSummary as HTML content for a WordPress post."""
    parts = [
        f"<p><em>{summary.citation}</em></p>",
        f"<h3>Research Question</h3><p>{summary.research_question}</p>",
        f"<h3>Key Finding</h3><p>{summary.key_finding}</p>",
        f"<h3>Study Design</h3><p>{summary.design}</p>",
        f"<h3>Primary Outcome</h3><p>{summary.primary_outcome}</p>",
        f"<h3>Limitations</h3><p>{summary.limitations}</p>",
    ]
    if summary.feedback_url:
        parts.append(
            f'<p><a href="{summary.feedback_url}">Provide feedback on this article</a></p>'
        )
    return "\n".join(parts)


def _create_post(
    summary: LiteratureSummary,
    api_base: str,
    auth_header: str,
    config: WordPressConfig,
    term_map: dict[str, int],
) -> int | None:
    """Create a single WordPress post for an article summary.

    Returns the post ID on success, None on failure.
    """
    html = _render_article_html(summary)
    term_ids = [term_map[t] for t in summary.tags if t in term_map]

    post_data: dict = {
        "title": summary.title,
        "content": html,
        "status": "publish",
        "meta": {
            "pmid": summary.pmid,
            "triage_score": str(summary.triage_score),
            "journal": summary.journal,
            "pub_date": summary.pub_date,
            "source_topic": summary.source_topic,
            "preindex": str(summary.preindex),
        },
    }

    # Attach taxonomy terms if any were resolved
    if term_ids:
        post_data[config.clinical_topics_taxonomy] = term_ids

    headers = {
        "Authorization": auth_header,
        "Content-Type": "application/json",
    }

    try:
        resp = httpx.post(
            f"{api_base}/posts",
            json=post_data,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        post_id = resp.json()["id"]
        logger.info("WordPress post created: PMID %s → post %d", summary.pmid, post_id)
        return post_id
    except Exception:
        logger.warning(
            "Failed to create WordPress post for PMID %s", summary.pmid, exc_info=True
        )
        return None
