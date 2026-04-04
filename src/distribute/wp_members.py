# owner: wp-publish
"""Query WordPress for member data and topic preferences.

Requires a custom REST endpoint on the WordPress site that exposes
member emails and their selected clinical topic preferences. See
docs/wordpress-setup.md for the PHP snippet that registers this endpoint.

The custom endpoint returns:
    [{"email": "...", "display_name": "...", "topics": ["Acute Treatment", ...]}]
"""

import logging
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)


@dataclass
class Member:
    """A WordPress site member with topic preferences."""

    email: str
    display_name: str = ""
    topics: list[str] = field(default_factory=list)


def fetch_members(site_url: str, api_secret: str | None = None) -> list[Member]:
    """Fetch members and their topic preferences from WordPress.

    Calls the custom REST endpoint GET /wp-json/digest/v1/members
    which must be registered on the WordPress site.

    Args:
        site_url: WordPress site URL (no trailing slash).
        api_secret: Optional shared secret for endpoint authentication.
            Sent as X-Digest-Secret header if provided.

    Returns:
        List of Member objects with email and topic preferences.
    """
    url = f"{site_url.rstrip('/')}/wp-json/digest/v1/members"
    headers: dict[str, str] = {}
    if api_secret:
        headers["X-Digest-Secret"] = api_secret

    try:
        resp = httpx.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        logger.warning("Failed to fetch members from %s", url, exc_info=True)
        return []

    members = []
    for item in data:
        if not item.get("email"):
            continue
        members.append(
            Member(
                email=item["email"],
                display_name=item.get("display_name", ""),
                topics=item.get("topics", []),
            )
        )

    logger.info("Fetched %d members from WordPress", len(members))
    return members
