# owner: email-send
"""Send the assembled email digest via Resend API."""

import logging
import os

import resend

from src.models import EmailConfig, EmailDigest, SubscriberDigest

logger = logging.getLogger(__name__)


def send_digest(digest: EmailDigest, config: EmailConfig) -> bool:
    """Send the digest email to configured recipients.

    Args:
        digest: Assembled EmailDigest with markdown and plain_text content.
        config: EmailConfig with sender, recipients, and subject template.

    Returns:
        True if the email was sent successfully, False otherwise.
    """
    if not config.enabled:
        logger.info("Email sending disabled (enabled: false), skipping")
        return False

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


def send_subscriber_digests(
    subscriber_digests: list[SubscriberDigest],
    config: EmailConfig,
) -> int:
    """Send personalized digests to each subscriber.

    Args:
        subscriber_digests: Per-subscriber digests built by build_subscriber_digests.
        config: EmailConfig with sender and subject template.

    Returns:
        Number of emails sent successfully.
    """
    if not config.enabled:
        logger.info("Email sending disabled (enabled: false), skipping")
        return 0

    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        logger.warning("RESEND_API_KEY not set, skipping email send")
        return 0

    resend.api_key = api_key
    sent = 0

    for sd in subscriber_digests:
        subject = config.subject.format(
            date_range=sd.digest.date_range,
            article_count=sd.digest.article_count,
        )
        try:
            params: resend.Emails.SendParams = {
                "from": config.from_address,
                "to": [sd.subscriber.email],
                "subject": subject,
                "html": _markdown_to_html(sd.digest.markdown),
                "text": sd.digest.plain_text,
            }
            result = resend.Emails.send(params)
            logger.info(
                "Email sent to %s (id: %s)",
                sd.subscriber.email,
                result.get("id", "unknown"),
            )
            sent += 1
        except Exception:
            logger.warning(
                "Failed to send email to %s", sd.subscriber.email, exc_info=True
            )

    return sent


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

        # Skip empty lines — <p> tags and <hr> provide spacing
        if not stripped:
            continue

        # Regular text with inline formatting
        html_lines.append(f"<p>{_inline_format(stripped)}</p>")

    if in_list:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


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
