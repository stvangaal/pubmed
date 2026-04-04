# owner: ai-evaluation
"""Fetch and cache PubMed records by PMID for evaluation tests.

Gold standard datasets store PMIDs only (no abstracts) for copyright
reasons.  This module fetches article content at evaluation runtime
and caches it locally to avoid redundant API calls.
"""

import json
import logging
import os
import xml.etree.ElementTree as ET
from pathlib import Path

from src.models import PubmedRecord
from src.search.pubmed_query import efetch, parse_record

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "eval" / ".cache"


def fetch_records(pmids: list[str], use_cache: bool = True) -> list[PubmedRecord]:
    """Fetch PubmedRecord objects for a list of PMIDs.

    Checks the local cache first (data/eval/.cache/) to avoid redundant
    PubMed API calls.  Fetches missing records from PubMed and caches them.

    Args:
        pmids: List of PubMed IDs to fetch.
        use_cache: Whether to use/update the local cache.

    Returns:
        List of PubmedRecord objects (order matches input PMIDs where possible).
    """
    cached: dict[str, PubmedRecord] = {}
    to_fetch: list[str] = []

    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        for pmid in pmids:
            record = _load_cached(pmid)
            if record is not None:
                cached[pmid] = record
            else:
                to_fetch.append(pmid)
    else:
        to_fetch = list(pmids)

    if to_fetch:
        logger.info("Fetching %d records from PubMed API", len(to_fetch))
        fetched = _fetch_from_pubmed(to_fetch)
        if use_cache:
            for record in fetched:
                _save_cached(record)
        for record in fetched:
            cached[record.pmid] = record

    # Return in input order, skipping any that couldn't be fetched
    results = []
    for pmid in pmids:
        if pmid in cached:
            results.append(cached[pmid])
        else:
            logger.warning("Could not fetch PMID %s", pmid)
    return results


def _fetch_from_pubmed(pmids: list[str]) -> list[PubmedRecord]:
    """Fetch records from PubMed API via efetch + parse_record."""
    if not pmids:
        return []

    xml_data = efetch(pmids, rate_limit_delay=0.4)
    root = ET.fromstring(xml_data)
    articles = root.findall(".//PubmedArticle")

    records = []
    for article in articles:
        record = parse_record(article)
        if record is not None:
            records.append(record)

    logger.info("Fetched %d of %d requested PMIDs", len(records), len(pmids))
    return records


def _cache_path(pmid: str) -> Path:
    """Path to the cached JSON file for a PMID."""
    return CACHE_DIR / f"{pmid}.json"


def _load_cached(pmid: str) -> PubmedRecord | None:
    """Load a cached PubmedRecord from disk."""
    path = _cache_path(pmid)
    if not path.exists():
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        return PubmedRecord(**data)
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        logger.warning("Cache miss for PMID %s (corrupt): %s", pmid, e)
        return None


def _save_cached(record: PubmedRecord) -> None:
    """Save a PubmedRecord to the local cache as JSON."""
    path = _cache_path(record.pmid)
    data = {
        "pmid": record.pmid,
        "title": record.title,
        "authors": record.authors,
        "journal": record.journal,
        "abstract": record.abstract,
        "pub_date": record.pub_date,
        "article_types": record.article_types,
        "mesh_terms": record.mesh_terms,
        "language": record.language,
        "doi": record.doi,
        "status": "retrieved",
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
