# owner: wp-publish
"""End-to-end WordPress publishing test.

Runs the pipeline stages (search → filter → triage → summarize → WP publish)
with safe overrides:
  - Small search scope (3-day window, 30 results, max 3 articles)
  - Draft status (posts invisible to site visitors)
  - No email, no blog publish, no seen-pmids mutation

Usage:
    # Run the e2e test (publishes drafts to WordPress)
    python3.14 scripts/e2e_wp_test.py --domain stroke

    # Clean up: delete previously created draft posts
    python3.14 scripts/e2e_wp_test.py --domain stroke --cleanup

Requires env vars: WP_{DOMAIN}_USERNAME, WP_{DOMAIN}_APP_PASSWORD, ANTHROPIC_API_KEY
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from src.config import (
    check_domain_schema,
    load_filter_config,
    load_search_config,
    load_summary_config,
    load_wp_config,
)
from src.distribute.wp_publish import _build_auth_header, publish_to_wordpress
from src.filter.llm_triage import llm_triage
from src.filter.rule_filter import rule_filter
from src.search.pubmed_query import multi_search
from src.summarize.llm_summarize import summarize

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("e2e-wp-test")

# File to persist created post IDs for cleanup
_STATE_DIR = Path("data/e2e-test")


def _state_file(domain: str) -> Path:
    return _STATE_DIR / f"{domain}-wp-posts.json"


def _save_post_ids(domain: str, post_ids: dict[str, int]) -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = _state_file(domain)
    path.write_text(json.dumps(post_ids, indent=2))
    logger.info("Saved %d post IDs to %s", len(post_ids), path)


def _load_post_ids(domain: str) -> dict[str, int]:
    path = _state_file(domain)
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def run_test(domain: str) -> None:
    """Run pipeline stages with safe overrides, publish drafts to WordPress."""
    check_domain_schema(domain)

    # Load configs
    search_config = load_search_config(domain=domain)
    filter_config = load_filter_config(domain=domain)
    summary_config = load_summary_config(domain=domain)
    wp_config = load_wp_config(domain=domain)

    # Safe overrides
    search_config.date_window_days = 3
    search_config.retmax = 30
    filter_config.llm_triage.max_articles = 3
    wp_config.post_status = "draft"

    if not wp_config.enabled:
        logger.error("WordPress is disabled for domain '%s'. Check wp-config.yaml.", domain)
        sys.exit(1)

    run_date = datetime.now()

    # --- Stage 1: Search ---
    logger.info("Stage 1: PubMed search (3-day window, retmax=30)")
    records, total = multi_search(
        search_config,
        run_date=run_date,
        preindex_journals=filter_config.priority_journals,
    )
    logger.info("  Found %d records (%d total in PubMed)", len(records), total)

    if not records:
        logger.warning("No records found. Try increasing date_window_days. Exiting.")
        sys.exit(0)

    # --- Stage 2a: Rule filter ---
    logger.info("Stage 2a: Rule filter")
    passed, excluded = rule_filter(records, filter_config.rule_filter)
    logger.info("  %d passed, %d excluded", len(passed), len(excluded))

    if not passed:
        logger.warning("No records passed rule filter. Exiting.")
        sys.exit(0)

    # --- Stage 2b: LLM triage ---
    logger.info("Stage 2b: LLM triage (max 3 articles)")
    topic_prompts = {
        t.name: t.triage_prompt_file
        for t in search_config.topics
        if t.triage_prompt_file
    }
    above, below, triage_usage = llm_triage(
        passed,
        filter_config.llm_triage,
        seen_pmids_path=filter_config.llm_triage.seen_pmids_file,
        topic_prompts=topic_prompts or None,
        readonly_seen_pmids=True,  # Don't mutate seen-pmids
    )
    logger.info("  %d above threshold, %d below", len(above), len(below))
    logger.info("  Triage cost: $%.4f", triage_usage.estimated_cost)

    if not above:
        logger.warning("No articles above triage threshold. Exiting.")
        sys.exit(0)

    # --- Stage 3: Summarize ---
    logger.info("Stage 3: Summarize")
    summaries, summarize_usage = summarize(above, summary_config)
    logger.info("  Generated %d summaries", len(summaries))
    logger.info("  Summarization cost: $%.4f", summarize_usage.estimated_cost)

    # --- Stage 4: WordPress publish (as draft) ---
    logger.info("Stage 4: WordPress publish (status=draft)")
    wp_posts = publish_to_wordpress(summaries, wp_config)

    if wp_posts:
        logger.info("  Created %d draft posts:", len(wp_posts))
        for pmid, post_id in wp_posts.items():
            logger.info("    PMID %s → post %d", pmid, post_id)
        _save_post_ids(domain, wp_posts)
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Check drafts in WP admin: %s/wp-admin/edit.php", wp_config.site_url)
        logger.info("  2. Verify title, content, taxonomy terms, and meta fields")
        logger.info("  3. Promote good articles to 'publish' or clean up with --cleanup")
    else:
        logger.error("  No posts created. Check logs above for errors.")
        sys.exit(1)


def cleanup(domain: str) -> None:
    """Delete previously created test posts from WordPress."""
    wp_config = load_wp_config(domain=domain)
    post_ids = _load_post_ids(domain)

    if not post_ids:
        logger.info("No saved post IDs found for domain '%s'. Nothing to clean up.", domain)
        return

    username = os.environ.get(wp_config.env_username)
    app_password = os.environ.get(wp_config.env_app_password)
    if not username or not app_password:
        logger.error("WordPress credentials not set. Cannot clean up.")
        sys.exit(1)

    auth_header = _build_auth_header(username, app_password)
    api_base = f"{wp_config.site_url.rstrip('/')}/wp-json/wp/v2"

    deleted = 0
    for pmid, post_id in post_ids.items():
        try:
            resp = httpx.delete(
                f"{api_base}/posts/{post_id}",
                params={"force": "true"},
                headers={"Authorization": auth_header},
                timeout=30,
            )
            resp.raise_for_status()
            logger.info("  Deleted post %d (PMID %s)", post_id, pmid)
            deleted += 1
        except Exception:
            logger.warning("  Failed to delete post %d (PMID %s)", post_id, pmid, exc_info=True)

    logger.info("Deleted %d/%d posts", deleted, len(post_ids))

    # Remove state file
    state_path = _state_file(domain)
    if state_path.exists():
        state_path.unlink()
        logger.info("Removed state file: %s", state_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="E2E WordPress publishing test")
    parser.add_argument("--domain", required=True, help="Domain (e.g., stroke)")
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete previously created test posts instead of running the test",
    )
    args = parser.parse_args()

    if args.cleanup:
        cleanup(args.domain)
    else:
        run_test(args.domain)


if __name__ == "__main__":
    main()
