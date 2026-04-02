# owner: digest-build
"""Upload digest and articles to Supabase for the archive."""

import logging
import os

import httpx

from src.models import EmailDigest, LiteratureSummary

logger = logging.getLogger(__name__)


def upload_digest(
    domain: str,
    run_date: str,
    digest: EmailDigest,
    summaries: list[LiteratureSummary],
    blog_url: str = "",
) -> bool:
    """Upload a completed digest and its articles to Supabase.

    No-op if SUPABASE_URL is not set (backwards-compatible).

    Args:
        domain: Domain name (e.g. "stroke").
        run_date: ISO date string (YYYY-MM-DD).
        digest: The assembled EmailDigest.
        summaries: List of LiteratureSummary objects from this run.
        blog_url: Optional URL to the published blog page.

    Returns:
        True if upload succeeded, False otherwise.
    """
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY")

    if not supabase_url or not service_key:
        logger.debug("Supabase not configured, skipping digest upload")
        return False

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    rest_url = f"{supabase_url}/rest/v1"

    try:
        # Upsert digest row (domain + run_date is unique)
        digest_payload = {
            "domain": domain,
            "run_date": run_date,
            "article_count": digest.article_count,
            "content_html": _markdown_to_html_simple(digest.markdown),
            "content_markdown": digest.markdown,
            "blog_url": blog_url,
        }
        resp = httpx.post(
            f"{rest_url}/digests",
            json=digest_payload,
            headers={
                **headers,
                "Prefer": "return=representation,resolution=merge-duplicates",
            },
            timeout=15,
        )
        resp.raise_for_status()
        digest_row = resp.json()
        digest_id = digest_row[0]["id"] if isinstance(digest_row, list) else digest_row["id"]

        # Insert articles
        if summaries:
            articles_payload = [
                {
                    "digest_id": digest_id,
                    "pmid": s.pmid,
                    "title": s.title,
                    "journal": s.journal,
                    "pub_date": s.pub_date,
                    "subdomain": s.subdomain,
                    "triage_score": s.triage_score,
                    "summary_short": s.summary_short,
                    "summary_full": _build_full_summary(s),
                    "doi": None,  # DOI not on LiteratureSummary currently
                }
                for s in summaries
            ]
            resp = httpx.post(
                f"{rest_url}/articles",
                json=articles_payload,
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()

        logger.info(
            "Uploaded digest for %s/%s (%d articles) to Supabase",
            domain,
            run_date,
            len(summaries),
        )
        return True

    except Exception:
        logger.warning("Failed to upload digest to Supabase", exc_info=True)
        return False


def _build_full_summary(s: LiteratureSummary) -> str:
    """Build a readable full summary string from a LiteratureSummary."""
    parts = [
        f"**Research Question:** {s.research_question}",
        f"**Key Finding:** {s.key_finding}",
        f"**Design:** {s.design}",
        f"**Primary Outcome:** {s.primary_outcome}",
        f"**Limitations:** {s.limitations}",
    ]
    return "\n".join(parts)


def _markdown_to_html_simple(markdown: str) -> str:
    """Minimal markdown-to-HTML for storage. Reuses email_send logic."""
    from src.distribute.email_send import _markdown_to_html

    return _markdown_to_html(markdown)
