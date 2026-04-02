# owner: email-send
"""Query subscribers from Supabase for a given domain."""

import logging
import os

import httpx

logger = logging.getLogger(__name__)


def get_subscribers(domain: str) -> list[str]:
    """Fetch active subscriber emails for a domain from Supabase.

    Requires SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables.

    Args:
        domain: The domain name (e.g. "stroke", "neurology").

    Returns:
        List of subscriber email addresses. Empty list if Supabase
        is not configured or the query fails.
    """
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY")

    if not supabase_url or not service_key:
        logger.warning(
            "SUPABASE_URL or SUPABASE_SERVICE_KEY not set, "
            "cannot query subscribers"
        )
        return []

    # Query active subscriptions for this domain, joining auth.users for email.
    # Uses PostgREST API via Supabase REST endpoint.
    # We call an RPC function to join subscriptions with auth.users (since
    # auth.users is not directly queryable via PostgREST).
    url = f"{supabase_url}/rest/v1/rpc/get_subscriber_emails"
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    payload = {"target_domain": domain}

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        rows = resp.json()
        emails = [row["email"] for row in rows if row.get("email")]
        logger.info(
            "Fetched %d subscriber(s) for domain '%s' from Supabase",
            len(emails),
            domain,
        )
        return emails
    except Exception:
        logger.warning(
            "Failed to query subscribers from Supabase", exc_info=True
        )
        return []
