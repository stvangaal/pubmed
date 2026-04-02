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

from src.models import PubmedRecord, SearchConfig, Topic
from src.search.date_normalize import normalize_pub_date

logger = logging.getLogger(__name__)

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


# ---------------------------------------------------------------------------
# Query construction
# ---------------------------------------------------------------------------

def _date_range(
    config: SearchConfig, run_date: datetime | None = None,
) -> tuple[str, str]:
    """Compute the (mindate, maxdate) strings for a search window.

    The end date is run_date minus 1 day (exclusive) to prevent overlap
    between consecutive runs. The start date is run_date minus
    date_window_days.  PubMed date ranges are inclusive on both ends.

    Returns dates formatted as YYYY/MM/DD for the esearch API.
    """
    if run_date is None:
        run_date = datetime.now()
    start = run_date - timedelta(days=config.date_window_days)
    end = run_date - timedelta(days=1)
    return start.strftime("%Y/%m/%d"), end.strftime("%Y/%m/%d")


def build_query(config: SearchConfig) -> str:
    """Build the term part of a PubMed MeSH query from a SearchConfig.

    Combines MeSH terms with OR and adds any additional free-text terms.
    Date filtering is handled separately via esearch API parameters
    (datetype, mindate, maxdate) — not embedded in the query string.

    Example output:
        "stroke"[MeSH Major Topic]
    """
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

    return " AND ".join(parts)


def build_preindex_query(
    config: SearchConfig,
    journals: list[str],
) -> str:
    """Build a Title/Abstract query limited to specific journals.

    Used to catch recently published articles before MeSH indexing.
    Searches the same terms as build_query() but uses [Title/Abstract]
    instead of [MeSH Major Topic], restricted to the given journal list.
    Date filtering is handled separately via esearch API parameters.

    Example output:
        ("atrial fibrillation"[Title/Abstract]) AND
        ("N Engl J Med"[Journal] OR "Lancet"[Journal])
    """
    # Text terms — OR-joined, each wrapped with [Title/Abstract].
    text_clauses = [f'"{term}"[Title/Abstract]' for term in config.mesh_terms]
    if config.additional_terms:
        text_clauses.extend(
            f'"{term}"[Title/Abstract]' for term in config.additional_terms
        )
    text_part = " OR ".join(text_clauses)
    if len(text_clauses) > 1:
        text_part = f"({text_part})"

    # Journal filter — OR-joined.
    journal_clauses = [f'"{j}"[Journal]' for j in journals]
    journal_part = " OR ".join(journal_clauses)
    if len(journal_clauses) > 1:
        journal_part = f"({journal_part})"

    return f"{text_part} AND {journal_part}"


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------

def esearch(
    query: str,
    retmax: int = 200,
    rate_limit_delay: float = 0.4,
    api_key: str | None = None,
    datetype: str | None = None,
    mindate: str | None = None,
    maxdate: str | None = None,
) -> tuple[list[str], int]:
    """Call PubMed's esearch endpoint to get PMIDs matching a query.

    Date filtering uses esearch API parameters (not inline query syntax):
    - datetype: "mhda" (MeSH date), "edat" (entry date), or "pdat" (pub date)
    - mindate/maxdate: YYYY/MM/DD format

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
    if datetype:
        params["datetype"] = datetype
    if mindate:
        params["mindate"] = mindate
    if maxdate:
        params["maxdate"] = maxdate

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

def _execute_query(
    query: str,
    retmax: int = 200,
    rate_limit_delay: float = 0.4,
    api_key: str | None = None,
    require_abstract: bool = True,
    datetype: str | None = None,
    mindate: str | None = None,
    maxdate: str | None = None,
) -> tuple[list[PubmedRecord], int]:
    """Execute a pre-built PubMed query through esearch, efetch, and parse.

    Shared by both MeSH-based search() and preindex searches in
    multi_search().  Callers build the query string; this function
    handles the API round-trips and XML parsing.

    Date filtering is applied via esearch API parameters (datetype,
    mindate, maxdate) rather than inline query syntax.

    Returns (records, total_count).
    """
    logger.info("Executing query: %s (datetype=%s)", query, datetype)

    pmids, total_count = esearch(
        query,
        retmax=retmax,
        rate_limit_delay=rate_limit_delay,
        api_key=api_key,
        datetype=datetype,
        mindate=mindate,
        maxdate=maxdate,
    )

    if not pmids:
        logger.info("No results returned by esearch")
        return [], total_count

    batch_size = 200
    records: list[PubmedRecord] = []

    for i in range(0, len(pmids), batch_size):
        batch = pmids[i : i + batch_size]
        xml_data = efetch(
            batch,
            rate_limit_delay=rate_limit_delay,
            api_key=api_key,
        )

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

            if require_abstract and not record.abstract:
                logger.info(
                    "Excluding PMID %s: missing abstract", record.pmid
                )
                continue

            records.append(record)

    logger.info(
        "Query complete: %d records returned (esearch total: %d)",
        len(records),
        total_count,
    )
    return records, total_count


def search(
    config: SearchConfig,
    run_date: datetime | None = None,
) -> tuple[list[PubmedRecord], int]:
    """Run the full PubMed search pipeline.

    1. Build query from config (terms only, no date in query string).
    2. Call esearch with datetype=mhda to filter by MeSH indexing date.
    3. Call efetch (in batches of 200) to get full XML.
    4. Parse each article into a PubmedRecord.
    5. Exclude articles without abstracts if require_abstract is True.

    Uses datetype="mhda" (MeSH date) so articles are found when they
    become MeSH-searchable, not when they first entered PubMed.

    Returns (records, total_count) where total_count is the number
    reported by esearch (useful for logging/metrics).
    """
    query = build_query(config)
    mindate, maxdate = _date_range(config, run_date)
    return _execute_query(
        query,
        retmax=config.retmax,
        rate_limit_delay=config.rate_limit_delay,
        api_key=config.api_key,
        require_abstract=config.require_abstract,
        datetype="mhda",
        mindate=mindate,
        maxdate=maxdate,
    )


def multi_search(
    config: SearchConfig,
    run_date: datetime | None = None,
    preindex_journals: list[str] | None = None,
) -> tuple[list[PubmedRecord], int]:
    """Run primary search plus any configured topics, deduplicate.

    Each topic runs as an independent PubMed query using its own
    mesh_terms/additional_terms but inheriting date_window_days, retmax,
    require_abstract, rate_limit_delay, and api_key from the parent config.

    Results are deduplicated by PMID (first-seen wins).  Each record is
    tagged with source_topic indicating which topic found it.

    When config.mesh_terms is non-empty, a primary search runs first
    (tagged source_topic="primary") for backward compatibility.

    When preindex_journals is provided, a parallel Title/Abstract search
    runs for each topic (and primary) limited to the given journals.
    These catch articles before MeSH indexing.  MeSH searches run first
    so indexed hits take priority during dedup.  Preindex-only hits are
    tagged with preindex=True.
    """
    all_records: list[PubmedRecord] = []
    seen_pmids: set[str] = set()
    total = 0

    # Primary search (backward compat — runs when top-level mesh_terms set)
    if config.mesh_terms:
        primary_records, primary_total = search(config, run_date)
        total += primary_total
        for r in primary_records:
            r.source_topic = "primary"
            seen_pmids.add(r.pmid)
        all_records.extend(primary_records)

    # Topic searches
    for topic in config.topics:
        topic_config = SearchConfig(
            mesh_terms=topic.mesh_terms,
            additional_terms=topic.additional_terms,
            date_window_days=config.date_window_days,
            retmax=config.retmax,
            require_abstract=config.require_abstract,
            rate_limit_delay=config.rate_limit_delay,
            api_key=config.api_key,
        )
        logger.info("Running topic search: %s", topic.name)
        records, count = search(topic_config, run_date)
        total += count
        new_count = 0
        for r in records:
            if r.pmid not in seen_pmids:
                r.source_topic = topic.name
                seen_pmids.add(r.pmid)
                all_records.append(r)
                new_count += 1
        logger.info(
            "Topic '%s': %d results, %d new (after dedup)",
            topic.name, len(records), new_count,
        )

    # --- Preindex searches (Title/Abstract, journal-limited) ---
    if preindex_journals:
        preindex_count = 0

        # Collect all (source_topic, SearchConfig) pairs to run.
        preindex_targets: list[tuple[str, SearchConfig]] = []
        if config.mesh_terms:
            preindex_targets.append(("primary", config))
        for topic in config.topics:
            preindex_targets.append((
                topic.name,
                SearchConfig(
                    mesh_terms=topic.mesh_terms,
                    additional_terms=topic.additional_terms,
                    date_window_days=config.date_window_days,
                    retmax=config.retmax,
                    require_abstract=config.require_abstract,
                    rate_limit_delay=config.rate_limit_delay,
                    api_key=config.api_key,
                ),
            ))

        for topic_name, topic_cfg in preindex_targets:
            query = build_preindex_query(topic_cfg, preindex_journals)
            mindate, maxdate = _date_range(topic_cfg, run_date)
            logger.info("Running preindex search: %s", topic_name)
            records, count = _execute_query(
                query,
                retmax=topic_cfg.retmax,
                rate_limit_delay=topic_cfg.rate_limit_delay,
                api_key=topic_cfg.api_key,
                require_abstract=topic_cfg.require_abstract,
                datetype="edat",
                mindate=mindate,
                maxdate=maxdate,
            )
            total += count
            new_count = 0
            for r in records:
                if r.pmid not in seen_pmids:
                    r.source_topic = topic_name
                    r.preindex = True
                    seen_pmids.add(r.pmid)
                    all_records.append(r)
                    new_count += 1
            preindex_count += new_count
            logger.info(
                "Preindex '%s': %d results, %d new (after dedup)",
                topic_name, len(records), new_count,
            )

        logger.info(
            "Preindex searches complete: %d new records from %d queries",
            preindex_count, len(preindex_targets),
        )

    logger.info(
        "Multi-search complete: %d total records (from %d topics%s%s)",
        len(all_records), len(config.topics),
        " + primary" if config.mesh_terms else "",
        " + preindex" if preindex_journals else "",
    )
    return all_records, total
