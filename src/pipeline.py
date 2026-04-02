# owner: project-infrastructure
"""Pipeline orchestrator — runs all stages end-to-end."""

import argparse
import logging
import sys
from datetime import datetime, timedelta

from src.config import (
    check_domain_schema,
    load_search_config,
    load_filter_config,
    load_summary_config,
    load_distribute_config,
    load_blog_config,
    load_email_config,
)
from src.search.pubmed_query import multi_search
from src.filter.rule_filter import rule_filter
from src.filter.llm_triage import llm_triage
from src.summarize.llm_summarize import summarize
from src.distribute.blog_publish import publish_blog
from src.distribute.digest_build import build_digest
from src.distribute.email_send import send_digest, send_rejection_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pipeline")


def _make_date_range(run_date: datetime, window_days: int) -> str:
    """Format a human-readable date range string."""
    start = run_date - timedelta(days=window_days)
    end = run_date - timedelta(days=1)
    return f"{start.strftime('%b %d')} – {end.strftime('%b %d, %Y')}"


def run():
    """Run the full pipeline: search → filter → summarize → blog → digest."""

    parser = argparse.ArgumentParser(description="PubMed Monitor pipeline")
    parser.add_argument(
        "--domain",
        default=None,
        help="Domain config profile (e.g. stroke, neurology). "
             "Omit to use the legacy flat config/ layout.",
    )
    args = parser.parse_args()
    domain = args.domain

    logger.info("Starting PubMed Monitor pipeline (domain: %s)", domain or "legacy")

    # --- Schema version check ---
    if domain:
        check_domain_schema(domain)

    # --- Load configs ---
    search_config = load_search_config(domain=domain)
    filter_config = load_filter_config(domain=domain)
    summary_config = load_summary_config(domain=domain)
    blog_config = load_blog_config(domain=domain)
    distribute_config = load_distribute_config(domain=domain)
    email_config = load_email_config(domain=domain)

    run_date = datetime.now()
    date_range = _make_date_range(run_date, search_config.date_window_days)
    run_date_str = run_date.strftime("%Y-%m-%d")

    # --- Stage 1: Search ---
    logger.info("Stage 1: Search")
    records, total = multi_search(
        search_config,
        run_date=run_date,
        preindex_journals=filter_config.priority_journals,
    )
    logger.info(f"  Retrieved {len(records)} records ({total} total in PubMed)")

    if not records:
        logger.warning("  No records found. Generating empty digest.")
        blog_page = publish_blog([], blog_config, date_range, run_date_str)
        build_digest([], distribute_config, date_range, blog_page)
        return

    # --- Stage 2: Filter (rule-based) ---
    logger.info("Stage 2a: Rule filter")
    passed, excluded = rule_filter(records, filter_config.rule_filter)
    logger.info(f"  {len(passed)} passed, {len(excluded)} excluded")

    if not passed:
        logger.warning("  No records passed rule filter. Generating empty digest.")
        blog_page = publish_blog([], blog_config, date_range, run_date_str)
        build_digest([], distribute_config, date_range, blog_page)
        return

    # --- Stage 2b: Filter (LLM triage) ---
    logger.info("Stage 2b: LLM triage")
    # Build per-topic prompt overrides from search config topics
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
    )
    logger.info(f"  {len(above)} above threshold, {len(below)} below")
    logger.info(f"  LLM triage cost: ${triage_usage.estimated_cost:.4f}")

    # --- Stage 3: Summarize ---
    logger.info("Stage 3: Summarize")
    summaries, summarize_usage = summarize(above, summary_config)
    logger.info(f"  Generated {len(summaries)} summaries")
    logger.info(f"  Summarization cost: ${summarize_usage.estimated_cost:.4f}")

    llm_usage = [triage_usage, summarize_usage]

    # --- Stage 4a: Blog publish ---
    logger.info("Stage 4a: Blog publish")
    blog_page = publish_blog(summaries, blog_config, date_range, run_date_str)
    if blog_page.published:
        logger.info(f"  Published to: {blog_page.page_url}")
    else:
        logger.info("  Blog page rendered but not published")

    # --- Stage 4b: Build email digest ---
    logger.info("Stage 4b: Build email digest")
    digest = build_digest(summaries, distribute_config, date_range, blog_page, llm_usage)
    logger.info(f"  Digest assembled: {digest.article_count} articles")
    logger.info(f"  Written to: {distribute_config.output.file}")

    # --- Stage 4c: Send email ---
    logger.info("Stage 4c: Send email")
    sent = send_digest(digest, email_config)
    if sent:
        logger.info("  Email sent to: %s", ", ".join(email_config.to_addresses))
    else:
        logger.info("  Email not sent (disabled, no key, or error)")

    # --- Stage 4d: Send troubleshooting report to owner ---
    logger.info("Stage 4d: Troubleshooting report")
    trouble_sent = send_rejection_report(
        below=below,
        config=email_config,
        date_range=date_range,
        score_threshold=filter_config.llm_triage.score_threshold,
        max_articles=filter_config.llm_triage.max_articles,
        llm_usage=llm_usage,
        min_articles=filter_config.llm_triage.min_articles,
        min_score_floor=filter_config.llm_triage.min_score_floor,
    )
    if trouble_sent:
        logger.info("  Troubleshooting report sent to: %s", email_config.owner_email)
    else:
        logger.info("  Troubleshooting report not sent (no owner, no key, or nothing to report)")

    logger.info("Pipeline complete")


if __name__ == "__main__":
    run()
