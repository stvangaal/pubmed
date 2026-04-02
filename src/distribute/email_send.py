# owner: email-send
"""Send the assembled email digest via Resend API."""

import logging
import os

import resend

from src.models import (
    BlogPage,
    DistributeConfig,
    EmailConfig,
    EmailDigest,
    LiteratureSummary,
    LLMUsage,
    PubmedRecord,
)

logger = logging.getLogger(__name__)


def send_digest(
    digest: EmailDigest,
    config: EmailConfig,
    summaries: list[LiteratureSummary] | None = None,
    distribute_config: DistributeConfig | None = None,
    blog_page: BlogPage | None = None,
) -> bool:
    """Send the digest email to configured recipients.

    When subscriber_source is "kit", creates a Kit broadcast with Liquid
    conditional blocks for per-subscriber topic filtering. Otherwise sends
    via Resend to the static to_addresses list.

    Args:
        digest: Assembled EmailDigest with markdown and plain_text content.
        config: EmailConfig with sender, recipients, and subject template.
        summaries: Raw summaries (required for Kit path).
        distribute_config: DistributeConfig (required for Kit path).
        blog_page: Optional BlogPage for article URLs (Kit path).

    Returns:
        True if the email was sent successfully, False otherwise.
    """
    if not config.enabled:
        logger.info("Email sending disabled (enabled: false), skipping")
        return False

    # --- Kit path: create broadcast with Liquid conditionals ---
    if config.subscriber_source == "kit":
        if summaries is None or distribute_config is None:
            logger.warning(
                "Kit mode requires summaries and distribute_config; "
                "falling back to Resend"
            )
        else:
            from src.distribute.kit_send import (
                build_kit_broadcast_html,
                send_kit_broadcast,
            )

            html = build_kit_broadcast_html(
                summaries, distribute_config, digest.date_range, blog_page
            )
            subject = config.subject.format(
                date_range=digest.date_range,
                article_count=digest.article_count,
            )
            return send_kit_broadcast(html, subject)

    # --- Resend path (default) ---
    if not config.to_addresses:
        logger.warning("No recipients configured in email-config.yaml, skipping")
        return False

    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        logger.warning("RESEND_API_KEY not set, skipping email send")
        return False

    resend.api_key = api_key

    subject = config.subject.format(
        date_range=digest.date_range,
        article_count=digest.article_count,
    )

    try:
        params: resend.Emails.SendParams = {
            "from": config.from_address,
            "to": config.to_addresses,
            "subject": subject,
            "html": _markdown_to_html(digest.markdown),
            "text": digest.plain_text,
        }
        result = resend.Emails.send(params)
        logger.info("Email sent successfully (id: %s)", result.get("id", "unknown"))
        return True
    except Exception:
        logger.warning("Failed to send email", exc_info=True)
        return False


def _markdown_to_html(markdown: str) -> str:
    """Convert markdown digest to basic HTML for email rendering.

    Uses simple line-by-line conversion — no external markdown library needed.
    Handles: bold, italic, links, horizontal rules, bullet lists, paragraphs.
    """
    import re

    lines = markdown.split("\n")
    html_lines = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        # Horizontal rule
        if stripped == "---":
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append("<hr>")
            continue

        # Bullet list items
        if stripped.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            item = _inline_format(stripped[2:])
            html_lines.append(f"<li>{item}</li>")
            continue

        # Close list if we hit a non-list line
        if in_list and not stripped.startswith("- "):
            html_lines.append("</ul>")
            in_list = False

        # Headings: ## text
        if stripped.startswith("## "):
            heading_text = _inline_format(stripped[3:])
            html_lines.append(f"<h2>{heading_text}</h2>")
            continue

        # Skip empty lines — <p> tags and <hr> provide spacing
        if not stripped:
            continue

        # Regular text with inline formatting
        html_lines.append(f"<p>{_inline_format(stripped)}</p>")

    if in_list:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


def _render_cost_lines(
    llm_usage: list[LLMUsage],
) -> tuple[list[str], list[str]]:
    """Render LLM cost breakdown as markdown and plain-text line lists."""
    if not llm_usage:
        return [], []

    total_cost = sum(u.estimated_cost for u in llm_usage)
    total_input = sum(u.input_tokens for u in llm_usage)
    total_output = sum(u.output_tokens for u in llm_usage)
    total_calls = sum(u.call_count for u in llm_usage)

    md: list[str] = ["\n**LLM Cost Summary**\n"]
    pt: list[str] = ["\nLLM Cost Summary\n"]

    for u in llm_usage:
        cache_note = ""
        if u.cache_read_input_tokens:
            cache_note = f" (cache hits: {u.cache_read_input_tokens:,} tokens)"
        md.append(
            f"- **{u.stage}** ({u.model}): "
            f"{u.call_count} calls, "
            f"{u.input_tokens:,} in / {u.output_tokens:,} out tokens"
            f"{cache_note} — ${u.estimated_cost:.4f}"
        )
        pt.append(
            f"- {u.stage} ({u.model}): "
            f"{u.call_count} calls, "
            f"{u.input_tokens:,} in / {u.output_tokens:,} out tokens"
            f"{cache_note} — ${u.estimated_cost:.4f}"
        )

    md.append(
        f"- **Total**: {total_calls} calls, "
        f"{total_input:,} in / {total_output:,} out tokens "
        f"— **${total_cost:.4f}**"
    )
    pt.append(
        f"- Total: {total_calls} calls, "
        f"{total_input:,} in / {total_output:,} out tokens "
        f"— ${total_cost:.4f}"
    )

    return md, pt


def build_rejection_report(
    below: list[PubmedRecord],
    date_range: str,
    score_threshold: float,
    max_articles: int,
    llm_usage: list[LLMUsage] | None = None,
    min_articles: int = 0,
    min_score_floor: float = 0.50,
) -> tuple[str, str]:
    """Build a troubleshooting report for articles that didn't make the cut.

    Splits the below list into near-misses (scored >= threshold but cut by
    the article cap) and below-threshold (scored < threshold).

    Returns:
        Tuple of (markdown, plain_text) content strings.
    """
    near_misses = sorted(
        [r for r in below if (r.triage_score or 0.0) >= score_threshold],
        key=lambda r: r.preindex,
    )
    below_thresh = sorted(
        [r for r in below if (r.triage_score or 0.0) < score_threshold],
        key=lambda r: r.preindex,
    )

    md_parts: list[str] = []
    pt_parts: list[str] = []

    md_parts.append(f"**Troubleshooting Report — {date_range}**")
    pt_parts.append(f"Troubleshooting Report — {date_range}")

    if min_articles > 0:
        md_parts.append(
            f"\n*Filter settings*: threshold={score_threshold}, "
            f"max={max_articles}, **min={min_articles}** (floor={min_score_floor})\n"
        )
        pt_parts.append(
            f"\nFilter settings: threshold={score_threshold}, "
            f"max={max_articles}, min={min_articles} (floor={min_score_floor})\n"
        )

    if near_misses:
        md_parts.append(
            f"\n**Near-Misses ({len(near_misses)})** — scored >= {score_threshold} "
            f"but cut by {max_articles}-article cap\n"
        )
        pt_parts.append(
            f"\nNear-Misses ({len(near_misses)}) — scored >= {score_threshold} "
            f"but cut by {max_articles}-article cap\n"
        )
        for r in near_misses:
            tag = " *(preindex)*" if r.preindex else ""
            tag_pt = " (preindex)" if r.preindex else ""
            md_parts.append(
                f"- **{r.title}** ({r.journal}){tag} — Score: {r.triage_score}\n"
                f"  Rationale: {r.triage_rationale}"
            )
            pt_parts.append(
                f"- {r.title} ({r.journal}){tag_pt} — Score: {r.triage_score}\n"
                f"  Rationale: {r.triage_rationale}"
            )

    if below_thresh:
        md_parts.append(
            f"\n**Below Threshold ({len(below_thresh)})** — scored < {score_threshold}\n"
        )
        pt_parts.append(
            f"\nBelow Threshold ({len(below_thresh)}) — scored < {score_threshold}\n"
        )
        for r in below_thresh:
            tag = " *(preindex)*" if r.preindex else ""
            tag_pt = " (preindex)" if r.preindex else ""
            md_parts.append(
                f"- **{r.title}** ({r.journal}){tag} — Score: {r.triage_score}\n"
                f"  Rationale: {r.triage_rationale}"
            )
            pt_parts.append(
                f"- {r.title} ({r.journal}){tag_pt} — Score: {r.triage_score}\n"
                f"  Rationale: {r.triage_rationale}"
            )

    if not near_misses and not below_thresh:
        md_parts.append("\nNo articles were rejected this run.")
        pt_parts.append("\nNo articles were rejected this run.")

    # --- LLM cost breakdown ---
    cost_md, cost_pt = _render_cost_lines(llm_usage or [])
    md_parts.extend(cost_md)
    pt_parts.extend(cost_pt)

    md_parts.append(
        "\n---\n"
        "*Curated by Dr. Stephen van Gaal.*\n"
        "\n"
        "*Article summaries in this digest are generated by AI and may contain "
        "errors or omissions. This content is intended for licensed healthcare "
        "professionals and is provided for informational and educational purposes "
        "only. It does not constitute medical advice, diagnosis, or treatment "
        "recommendations. Readers should verify important findings against "
        "primary sources before applying them to patient care.*\n"
        "\n"
        "*This report is sent only to the domain owner.*"
    )
    pt_parts.append(
        "\n---\n"
        "Curated by Dr. Stephen van Gaal.\n"
        "\n"
        "Article summaries in this digest are generated by AI and may contain "
        "errors or omissions. This content is intended for licensed healthcare "
        "professionals and is provided for informational and educational purposes "
        "only. It does not constitute medical advice, diagnosis, or treatment "
        "recommendations. Readers should verify important findings against "
        "primary sources before applying them to patient care.\n"
        "\n"
        "This report is sent only to the domain owner."
    )

    return "\n".join(md_parts), "\n".join(pt_parts)


def send_rejection_report(
    below: list[PubmedRecord],
    config: EmailConfig,
    date_range: str,
    score_threshold: float,
    max_articles: int,
    llm_usage: list[LLMUsage] | None = None,
    min_articles: int = 0,
    min_score_floor: float = 0.50,
) -> bool:
    """Send a troubleshooting report of rejected articles to the domain owner.

    Args:
        below: Articles that didn't make the cut (from LLM triage).
        config: EmailConfig with owner_email and sender info.
        date_range: Human-readable date range for the subject line.
        score_threshold: LLM triage score threshold.
        max_articles: Maximum articles allowed through triage.
        llm_usage: Optional list of LLMUsage objects for cost breakdown.
        min_articles: Minimum articles guarantee (0 = disabled).
        min_score_floor: Score floor for backfill eligibility.

    Returns:
        True if the email was sent successfully, False otherwise.
    """
    if not config.owner_email:
        logger.info("No owner_email configured, skipping troubleshooting report")
        return False

    if not below:
        logger.info("No rejected articles, skipping troubleshooting report")
        return False

    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        logger.warning("RESEND_API_KEY not set, skipping troubleshooting report")
        return False

    resend.api_key = api_key

    markdown, plain_text = build_rejection_report(
        below, date_range, score_threshold, max_articles, llm_usage,
        min_articles, min_score_floor,
    )

    subject = f"Troubleshooting Report — {date_range}"

    try:
        params: resend.Emails.SendParams = {
            "from": config.from_address,
            "to": [config.owner_email],
            "subject": subject,
            "html": _markdown_to_html(markdown),
            "text": plain_text,
        }
        result = resend.Emails.send(params)
        logger.info(
            "Troubleshooting report sent (id: %s)", result.get("id", "unknown")
        )
        return True
    except Exception:
        logger.warning("Failed to send troubleshooting report", exc_info=True)
        return False


def _inline_format(text: str) -> str:
    """Apply inline markdown formatting: bold, italic, links."""
    import re

    # Links: [text](url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    # Bold: **text**
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    # Italic: *text*
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    # Middle dot (used in short summary links)
    text = text.replace(" · ", " &middot; ")

    return text
