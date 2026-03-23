# owner: project-infrastructure
"""Pipeline orchestrator — runs all stages end-to-end."""

import logging
import sys
from datetime import datetime, timedelta

from src.config import (
    load_search_config,
    load_filter_config,
    load_summary_config,
    load_distribute_config,
)
from src.search.pubmed_query import search
from src.filter.rule_filter import rule_filter
from src.filter.llm_triage import llm_triage
from src.summarize.llm_summarize import summarize
from src.distribute.digest_build import build_digest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pipeline")


def run():
    """Run the full pipeline: search → filter → summarize → distribute."""

    logger.info("Starting PubMed Stroke Monitor pipeline")

    # --- Load configs ---
    search_config = load_search_config()
    filter_config = load_filter_config()
    summary_config = load_summary_config()
    distribute_config = load_distribute_config()

    # --- Stage 1: Search ---
    logger.info("Stage 1: Search")
    run_date = datetime.now()
    records, total = search(search_config, run_date=run_date)
    logger.info(f"  Retrieved {len(records)} records ({total} total in PubMed)")

    if not records:
        logger.warning("  No records found. Generating empty digest.")
        start = run_date - timedelta(days=search_config.date_window_days)
        date_range = f"{start.strftime('%b %d')} – {(run_date - timedelta(days=1)).strftime('%b %d, %Y')}"
        build_digest([], distribute_config, date_range)
        return

    # --- Stage 2: Filter (rule-based) ---
    logger.info("Stage 2a: Rule filter")
    passed, excluded = rule_filter(records, filter_config.rule_filter)
    logger.info(f"  {len(passed)} passed, {len(excluded)} excluded")

    if not passed:
        logger.warning("  No records passed rule filter. Generating empty digest.")
        start = run_date - timedelta(days=search_config.date_window_days)
        date_range = f"{start.strftime('%b %d')} – {(run_date - timedelta(days=1)).strftime('%b %d, %Y')}"
        build_digest([], distribute_config, date_range)
        return

    # --- Stage 2b: Filter (LLM triage) ---
    logger.info("Stage 2b: LLM triage")
    above, below = llm_triage(passed, filter_config.llm_triage)
    logger.info(f"  {len(above)} above threshold, {len(below)} below")

    # --- Stage 3: Summarize ---
    logger.info("Stage 3: Summarize")
    summaries = summarize(above, summary_config)
    logger.info(f"  Generated {len(summaries)} summaries")

    # --- Stage 4: Distribute ---
    logger.info("Stage 4: Build digest")
    start = run_date - timedelta(days=search_config.date_window_days)
    date_range = f"{start.strftime('%b %d')} – {(run_date - timedelta(days=1)).strftime('%b %d, %Y')}"
    digest = build_digest(summaries, distribute_config, date_range)
    logger.info(f"  Digest assembled: {digest.article_count} articles")
    logger.info(f"  Written to: {distribute_config.output.file}")

    logger.info("Pipeline complete")


if __name__ == "__main__":
    run()
