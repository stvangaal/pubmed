# owner: pubmed-query
"""Query PubMed's E-utilities API and parse results into PubmedRecord objects.

This module is the pipeline's entry point — it produces the raw candidate set
that all downstream stages operate on. It uses only standard library modules
(urllib.request, xml.etree.ElementTree) per decision PQ2 in the spec.
"""

import json
import logging
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from src.models import PubmedRecord, SearchConfig
from src.search.date_normalize import normalize_pub_date

logger = logging.getLogger(__name__)

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


# ---------------------------------------------------------------------------
# Query construction
# ---------------------------------------------------------------------------

def build_query(config: SearchConfig, run_date: datetime | None = None) -> str:
    """Build a PubMed query string from a SearchConfig.

    Combines MeSH terms with OR, adds any additional free-text terms,
    and appends a date range filter using [Date - Entry].

    The end date is run_date minus 1 day (exclusive) to prevent overlap
    between consecutive runs. The start date is run_date minus
    date_window_days.

    Example output:
        "stroke"[MeSH Major Topic] AND 2026/03/16:2026/03/22[Date - Entry]
    """
    if run_date is None:
        run_date = datetime.now()

    # MeSH terms — OR-joined, each wrapped in quotes with [MeSH Major Topic].
    mesh_clauses = [f'"{term}"[MeSH Major Topic]' for term in config.mesh_terms]
    mesh_part = " OR ".join(mesh_clauses)
    if len(mesh_clauses) > 1:
        mesh_part = f"({mesh_part})"

    parts = [mesh_part]

    # Additional free-text terms — OR-joined.
    if config.additional_terms:
        additional = " OR ".join(config.additional_terms)
        if len(config.additional_terms) > 1:
            additional = f"({additional})"
        parts.append(additional)

    # Date range: start = run_date - window, end = run_date - 1 day.
    # PubMed ranges are inclusive on both ends, so subtracting 1 from the
    # end date prevents the same article appearing in two consecutive runs.
    start_date = run_date - timedelta(days=config.date_window_days)
    end_date = run_date - timedelta(days=1)
    date_range = (
        f"{start_date.strftime('%Y/%m/%d')}:{end_date.strftime('%Y/%m/%d')}"
        f"[Date - Entry]"
    )
    parts.append(date_range)

    return " AND ".join(parts)


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------

def esearch(
    query: str,
    retmax: int = 200,
    rate_limit_delay: float = 0.4,
    api_key: str | None = None,
) -> tuple[list[str], int]:
    """Call PubMed's esearch endpoint to get PMIDs matching a query.

    Returns a tuple of (pmid_list, total_count). The total_count may be
    larger than len(pmid_list) when results exceed retmax.
    """
    time.sleep(rate_limit_delay)

    params: dict[str, str | int] = {
        "db": "pubmed",
        "term": query,
        "retmax": retmax,
        "retmode": "json",
    }
    if api_key:
        params["api_key"] = api_key

    url = f"{BASE_URL}/esearch.fcgi?{urllib.parse.urlencode(params)}"
    logger.info("esearch request: %s", url)

    with urllib.request.urlopen(url) as resp:
        data = json.loads(resp.read())

    result = data["esearchresult"]
    pmids = result["idlist"]
    count = int(result["count"])
    logger.info("esearch returned %d PMIDs (total count: %d)", len(pmids), count)
    return pmids, count


def efetch(
    pmids: list[str],
    rate_limit_delay: float = 0.4,
    api_key: str | None = None,
) -> str:
    """Call PubMed's efetch endpoint to retrieve full XML records.

    Returns the raw XML string for the given PMIDs.
    """
    time.sleep(rate_limit_delay)

    params: dict[str, str] = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "rettype": "xml",
        "retmode": "xml",
    }
    if api_key:
        params["api_key"] = api_key

    url = f"{BASE_URL}/efetch.fcgi?{urllib.parse.urlencode(params)}"
    logger.info("efetch request for %d PMIDs", len(pmids))

    with urllib.request.urlopen(url) as resp:
        return resp.read().decode("utf-8")


# ---------------------------------------------------------------------------
# XML parsing
# ---------------------------------------------------------------------------

def parse_record(article_elem: ET.Element) -> PubmedRecord | None:
    """Parse a single PubmedArticle XML element into a PubmedRecord.

    Returns None (and logs the reason) if the article is missing a PMID.
    Articles missing abstracts are still returned here — the caller
    decides whether to exclude them based on require_abstract.
    """
    # PMID — required; skip the article entirely if missing.
    pmid_el = article_elem.find(".//PMID")
    pmid = pmid_el.text if pmid_el is not None else None
    if not pmid:
        logger.warning("Skipping article: no PMID found")
        return None

    # Title — use itertext() to capture mixed content (e.g. <i> tags).
    title_el = article_elem.find(".//ArticleTitle")
    title = "".join(title_el.itertext()) if title_el is not None else ""

    # Authors — "LastName FirstInitial" format.
    authors: list[str] = []
    for author in article_elem.findall(".//Author"):
        last = author.find("LastName")
        first = author.find("ForeName")
        if last is not None and last.text:
            if first is not None and first.text:
                authors.append(f"{last.text} {first.text[0]}")
            else:
                authors.append(last.text)

    # Journal title.
    journal_el = article_elem.find(".//Journal/Title")
    journal = journal_el.text if journal_el is not None else ""

    # Abstract — join all AbstractText parts (handles structured abstracts).
    # Use itertext() on each part to capture any inline markup.
    abstract_parts = article_elem.findall(".//AbstractText")
    abstract = (
        " ".join("".join(p.itertext()) for p in abstract_parts)
        if abstract_parts
        else ""
    )

    # Publication date — delegated to the date_normalize module.
    pub_date = normalize_pub_date(article_elem)

    # Article types (e.g., "Journal Article", "Randomized Controlled Trial").
    article_types = [
        pt.text for pt in article_elem.findall(".//PublicationType") if pt.text
    ]

    # MeSH descriptor terms.
    mesh_terms = [
        mesh.text
        for mesh in article_elem.findall(".//MeshHeading/DescriptorName")
        if mesh.text
    ]

    # Language code (e.g., "eng").
    lang_el = article_elem.find(".//Language")
    language = lang_el.text if lang_el is not None else ""

    # DOI — look through ArticleId elements for IdType="doi".
    doi: str | None = None
    for id_el in article_elem.findall(".//ArticleId"):
        if id_el.get("IdType") == "doi":
            doi = id_el.text
            break

    return PubmedRecord(
        pmid=pmid,
        title=title,
        authors=authors,
        journal=journal,
        abstract=abstract,
        pub_date=pub_date,
        article_types=article_types,
        mesh_terms=mesh_terms,
        language=language,
        doi=doi,
        status="retrieved",
        triage_score=None,
        triage_rationale=None,
    )


# ---------------------------------------------------------------------------
# Main search orchestrator
# ---------------------------------------------------------------------------

def search(
    config: SearchConfig,
    run_date: datetime | None = None,
) -> tuple[list[PubmedRecord], int]:
    """Run the full PubMed search pipeline.

    1. Build query from config.
    2. Call esearch to get PMIDs.
    3. Call efetch (in batches of 200) to get full XML.
    4. Parse each article into a PubmedRecord.
    5. Exclude articles without abstracts if require_abstract is True.

    Returns (records, total_count) where total_count is the number
    reported by esearch (useful for logging/metrics).
    """
    query = build_query(config, run_date)
    logger.info("Constructed query: %s", query)

    # Step 1: esearch — get PMIDs.
    pmids, total_count = esearch(
        query,
        retmax=config.retmax,
        rate_limit_delay=config.rate_limit_delay,
        api_key=config.api_key,
    )

    if not pmids:
        logger.info("No results returned by esearch")
        return [], total_count

    # Step 2: efetch — fetch in batches of 200.
    batch_size = 200
    records: list[PubmedRecord] = []

    for i in range(0, len(pmids), batch_size):
        batch = pmids[i : i + batch_size]
        xml_data = efetch(
            batch,
            rate_limit_delay=config.rate_limit_delay,
            api_key=config.api_key,
        )

        # Parse XML into individual article elements.
        root = ET.fromstring(xml_data)
        articles = root.findall(".//PubmedArticle")
        logger.info(
            "Batch %d-%d: fetched %d articles",
            i, i + len(batch), len(articles),
        )

        for article in articles:
            record = parse_record(article)
            if record is None:
                continue

            # Exclude articles without abstracts when configured.
            if config.require_abstract and not record.abstract:
                logger.info(
                    "Excluding PMID %s: missing abstract", record.pmid
                )
                continue

            records.append(record)

    logger.info(
        "Search complete: %d records returned (esearch total: %d)",
        len(records),
        total_count,
    )
    return records, total_count
