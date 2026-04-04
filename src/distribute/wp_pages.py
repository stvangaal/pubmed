# owner: wp-pages
"""Sync static website pages from repo Markdown files to WordPress.

Each page is a Markdown file under content/pages/ with YAML frontmatter.
Domain-specific overrides take precedence over _defaults/.
Pages are upserted (created or updated) via the WordPress REST API.

Usage:
    python -m src.distribute.wp_pages --domain stroke [--dry-run]
"""

import argparse
import hashlib
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
import markdown
import yaml

from src.config import load_wp_config
from src.distribute.wp_publish import _build_auth_header
from src.models import WordPressConfig

logger = logging.getLogger(__name__)

CONTENT_DIR = Path("content/pages")
STATE_DIR = Path("data/domains")


# --- Content resolution ---


def resolve_page_path(slug: str, domain: str) -> Path | None:
    """Resolve a page slug to a file path via the override chain.

    Resolution order:
      1. content/pages/{domain}/{slug}.md
      2. content/pages/_defaults/{slug}.md

    Returns the path if found, None otherwise.
    """
    domain_path = CONTENT_DIR / domain / f"{slug}.md"
    if domain_path.exists():
        return domain_path

    default_path = CONTENT_DIR / "_defaults" / f"{slug}.md"
    if default_path.exists():
        return default_path

    return None


def parse_page_file(path: Path) -> tuple[dict, str]:
    """Parse a page Markdown file into frontmatter dict and body string.

    Expects YAML frontmatter delimited by --- lines at the top of the file.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    frontmatter = yaml.safe_load(parts[1]) or {}
    body = parts[2].strip()
    return frontmatter, body


def render_markdown_to_html(body: str) -> str:
    """Convert Markdown body to HTML wrapped in a wp:html block.

    The wp:html wrapper prevents the WordPress block editor from
    parsing and mangling the HTML.
    """
    html = markdown.markdown(body, extensions=["extra"])
    return f"<!-- wp:html -->\n{html}\n<!-- /wp:html -->"


def compute_content_sha(path: Path) -> str:
    """Compute SHA-256 hex digest of a file's contents."""
    content = path.read_bytes()
    return hashlib.sha256(content).hexdigest()


# --- State management ---


def _state_path(domain: str) -> Path:
    return STATE_DIR / domain / "wp-pages-state.yaml"


def load_state(domain: str) -> dict:
    """Load the page sync state for a domain.

    Returns a dict of slug → {wp_page_id, content_sha, last_synced}.
    """
    path = _state_path(domain)
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return data.get("pages", {})


def save_state(domain: str, pages_state: dict) -> None:
    """Save the page sync state for a domain."""
    path = _state_path(domain)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump({"pages": pages_state}, f, default_flow_style=False)


# --- WordPress API ---


def _find_existing_page(
    slug: str, api_base: str, headers: dict,
) -> tuple[int | None, str | None]:
    """Look up an existing WordPress page by slug.

    Returns (page_id, modified_timestamp) or (None, None) if not found.
    """
    try:
        resp = httpx.get(
            f"{api_base}/pages",
            params={"slug": slug, "per_page": 1},
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        pages = resp.json()
        if pages:
            return pages[0]["id"], pages[0].get("modified")
    except Exception:
        logger.warning("Failed to look up page '%s'", slug, exc_info=True)
    return None, None


def _create_page(
    slug: str,
    title: str,
    html: str,
    status: str,
    menu_order: int,
    api_base: str,
    headers: dict,
) -> int | None:
    """Create a new WordPress page. Returns the page ID or None on failure."""
    page_data = {
        "slug": slug,
        "title": title,
        "content": html,
        "status": status,
        "menu_order": menu_order,
    }
    try:
        resp = httpx.post(
            f"{api_base}/pages",
            json=page_data,
            headers={**headers, "Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        page_id = resp.json()["id"]
        logger.info("WordPress page created: '%s' → page %d", slug, page_id)
        return page_id
    except Exception:
        logger.warning("Failed to create page '%s'", slug, exc_info=True)
        return None


def _update_page(
    page_id: int,
    title: str,
    html: str,
    status: str,
    menu_order: int,
    api_base: str,
    headers: dict,
) -> bool:
    """Update an existing WordPress page. Returns True on success."""
    page_data = {
        "title": title,
        "content": html,
        "status": status,
        "menu_order": menu_order,
    }
    try:
        resp = httpx.post(
            f"{api_base}/pages/{page_id}",
            json=page_data,
            headers={**headers, "Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        logger.info("WordPress page updated: page %d", page_id)
        return True
    except Exception:
        logger.warning("Failed to update page %d", page_id, exc_info=True)
        return False


def _set_front_page(page_id: int, api_base: str, headers: dict) -> bool:
    """Set the WordPress static front page to the given page ID."""
    try:
        resp = httpx.post(
            f"{api_base}/settings",
            json={"show_on_front": "page", "page_on_front": page_id},
            headers={**headers, "Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        logger.info("WordPress front page set to page %d", page_id)
        return True
    except Exception:
        logger.warning("Failed to set front page to %d", page_id, exc_info=True)
        return False


# --- Main sync ---


def sync_pages(
    domain: str,
    config: WordPressConfig,
    dry_run: bool = False,
) -> dict[str, int]:
    """Sync all configured pages for a domain to WordPress.

    Args:
        domain: Domain name (e.g., "stroke").
        config: WordPressConfig with site_url and pages list.
        dry_run: If True, resolve and render but don't call API.

    Returns:
        Dict mapping slug to WordPress page ID for synced pages.
    """
    if not config.enabled:
        logger.info("WordPress publishing disabled (enabled: false), skipping")
        return {}

    if not config.site_url:
        logger.warning("WordPress site_url not configured, skipping")
        return {}

    if not config.pages:
        logger.info("No pages configured for domain '%s', skipping", domain)
        return {}

    username = os.environ.get("WP_USERNAME")
    app_password = os.environ.get("WP_APP_PASSWORD")

    if not dry_run and (not username or not app_password):
        logger.warning(
            "WP_USERNAME or WP_APP_PASSWORD not set, skipping page sync"
        )
        return {}

    api_base = f"{config.site_url.rstrip('/')}/wp-json/wp/v2"
    headers = {}
    if username and app_password:
        headers["Authorization"] = _build_auth_header(username, app_password)

    state = load_state(domain)
    synced: dict[str, int] = {}

    for slug in config.pages:
        page_path = resolve_page_path(slug, domain)
        if page_path is None:
            logger.warning(
                "No content file found for page '%s' in domain '%s'", slug, domain
            )
            continue

        frontmatter, body = parse_page_file(page_path)
        content_sha = compute_content_sha(page_path)
        title = frontmatter.get("title", slug.replace("-", " ").title())
        status = frontmatter.get("status", "publish")
        menu_order = frontmatter.get("menu_order", 0)

        # Check if content has changed
        slug_state = state.get(slug, {})
        if slug_state.get("content_sha") == content_sha:
            logger.debug("Page '%s' unchanged (SHA match), skipping", slug)
            page_id = slug_state.get("wp_page_id")
            if page_id:
                synced[slug] = page_id
            continue

        html = render_markdown_to_html(body)

        if dry_run:
            logger.info(
                "DRY RUN: would sync page '%s' from %s (%d chars HTML)",
                slug, page_path, len(html),
            )
            continue

        # Upsert: find existing page or use cached ID
        wp_page_id = slug_state.get("wp_page_id")
        if wp_page_id is None:
            wp_page_id, modified = _find_existing_page(slug, api_base, headers)
            if wp_page_id and modified and slug_state.get("last_synced"):
                # Warn if page was modified in WP after our last sync
                logger.warning(
                    "Page '%s' (id %d) was modified in WordPress after last sync. "
                    "Repo version will overwrite.",
                    slug, wp_page_id,
                )

        if wp_page_id:
            success = _update_page(
                wp_page_id, title, html, status, menu_order, api_base, headers,
            )
            if success:
                synced[slug] = wp_page_id
        else:
            new_id = _create_page(
                slug, title, html, status, menu_order, api_base, headers,
            )
            if new_id:
                wp_page_id = new_id
                synced[slug] = new_id

        # Update state
        if wp_page_id:
            state[slug] = {
                "wp_page_id": wp_page_id,
                "content_sha": content_sha,
                "last_synced": datetime.now(timezone.utc).isoformat(),
            }

    # Set front page if landing was synced
    if not dry_run and "landing" in synced:
        _set_front_page(synced["landing"], api_base, headers)

    # Save state
    if not dry_run:
        save_state(domain, state)

    logger.info(
        "WordPress pages: synced %d/%d for domain '%s'",
        len(synced), len(config.pages), domain,
    )
    return synced


# --- CLI entry point ---


def main() -> None:
    """CLI entry point for page sync."""
    parser = argparse.ArgumentParser(
        description="Sync static pages from repo to WordPress",
    )
    parser.add_argument(
        "--domain", required=True, help="Domain name (e.g., stroke)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Resolve and render pages but don't call WordPress API",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.dry_run else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = load_wp_config(domain=args.domain)
    sync_pages(args.domain, config, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
