# owner: spike (not governed — exploratory)
"""
Spike 2: PubMed Search & Schema Mapping
Tests PubMed E-utilities API queries and validates that responses
map cleanly to the pubmed-record definition.

Questions:
1. Do MeSH terms + article type filters return relevant stroke literature?
2. Does every pubmed-record field map to something in the API response?
3. What edge cases exist (missing abstracts, DOIs, dates, MeSH terms)?
4. What's the weekly volume for a typical stroke query?
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta


@dataclass
class PubmedRecord:
    """Mirrors the pubmed-record definition (v0)."""
    pmid: str
    title: str
    authors: list[str]
    journal: str
    abstract: str
    pub_date: str
    article_types: list[str]
    mesh_terms: list[str]
    language: str
    doi: str | None
    status: str
    triage_score: float | None
    triage_rationale: str | None


# --- Search Queries to Test ---

# Date window: last 7 days
today = datetime.now()
week_ago = today - timedelta(days=7)
date_range = f"{week_ago.strftime('%Y/%m/%d')}:{today.strftime('%Y/%m/%d')}"

# Query variations to test
QUERIES = {
    "broad_mesh": (
        f'"stroke"[MeSH Major Topic] AND {date_range}[Date - Entry]'
    ),
    "filtered_types": (
        f'"stroke"[MeSH Major Topic] '
        f'AND (randomized controlled trial[pt] OR meta-analysis[pt] '
        f'OR systematic review[pt] OR practice guideline[pt]) '
        f'AND {date_range}[Date - Entry]'
    ),
    "clinical_focused": (
        f'("stroke"[MeSH Major Topic] OR "brain ischemia"[MeSH Major Topic]) '
        f'AND (randomized controlled trial[pt] OR meta-analysis[pt] '
        f'OR systematic review[pt] OR clinical trial[pt]) '
        f'AND {date_range}[Date - Entry] '
        f'AND english[la]'
    ),
}

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _rate_limit():
    """Sleep briefly to respect PubMed's 3 req/sec limit."""
    time.sleep(0.4)


def esearch(query, retmax=200):
    """Search PubMed and return list of PMIDs."""
    _rate_limit()
    params = urllib.parse.urlencode({
        "db": "pubmed",
        "term": query,
        "retmax": retmax,
        "retmode": "json",
    })
    url = f"{BASE_URL}/esearch.fcgi?{params}"
    with urllib.request.urlopen(url) as resp:
        data = json.loads(resp.read())
    result = data["esearchresult"]
    return result["idlist"], int(result["count"])


def efetch(pmids):
    """Fetch full records for a list of PMIDs. Returns XML string."""
    _rate_limit()
    params = urllib.parse.urlencode({
        "db": "pubmed",
        "id": ",".join(pmids),
        "rettype": "xml",
        "retmode": "xml",
    })
    url = f"{BASE_URL}/efetch.fcgi?{params}"
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode("utf-8")


def parse_record(article_elem):
    """
    Attempt to parse a PubmedArticle XML element into a PubmedRecord.
    Returns (PubmedRecord, warnings) or (None, errors).
    """
    warnings = []

    # PMID
    pmid_el = article_elem.find(".//PMID")
    pmid = pmid_el.text if pmid_el is not None else None
    if not pmid:
        return None, ["No PMID found"]

    # Title
    title_el = article_elem.find(".//ArticleTitle")
    title = "".join(title_el.itertext()) if title_el is not None else ""
    if not title:
        warnings.append("Missing title")

    # Authors
    authors = []
    for author in article_elem.findall(".//Author"):
        last = author.find("LastName")
        first = author.find("ForeName")
        if last is not None and last.text:
            name = last.text
            if first is not None and first.text:
                name = f"{last.text} {first.text[0]}"
            authors.append(name)
    if not authors:
        warnings.append("No authors found")

    # Journal
    journal_el = article_elem.find(".//Journal/Title")
    journal = journal_el.text if journal_el is not None else ""
    if not journal:
        warnings.append("Missing journal title")

    # Abstract
    abstract_parts = article_elem.findall(".//AbstractText")
    abstract = " ".join("".join(p.itertext()) for p in abstract_parts) if abstract_parts else ""
    if not abstract:
        warnings.append("NO ABSTRACT — would be excluded by pipeline")

    # Publication date — try multiple locations
    pub_date = ""
    # Try ArticleDate first (electronic publication)
    date_el = article_elem.find(".//ArticleDate")
    if date_el is not None:
        y = date_el.find("Year")
        m = date_el.find("Month")
        d = date_el.find("Day")
        if y is not None and y.text:
            pub_date = y.text
            if m is not None and m.text:
                pub_date += f"-{m.text.zfill(2)}"
                if d is not None and d.text:
                    pub_date += f"-{d.text.zfill(2)}"
    # Fallback to PubDate
    if not pub_date:
        date_el = article_elem.find(".//PubDate")
        if date_el is not None:
            y = date_el.find("Year")
            m = date_el.find("Month")
            medline = date_el.find("MedlineDate")
            if y is not None and y.text:
                pub_date = y.text
                if m is not None and m.text:
                    # Month might be "Jan", "Feb" etc — normalize
                    pub_date += f"-{m.text}"
            elif medline is not None and medline.text:
                pub_date = medline.text
                warnings.append(f"Non-standard date format: {pub_date}")
    if not pub_date:
        warnings.append("Missing publication date")

    # Article types
    article_types = [
        pt.text for pt in article_elem.findall(".//PublicationType")
        if pt.text
    ]
    if not article_types:
        warnings.append("No publication types")

    # MeSH terms
    mesh_terms = []
    for mesh in article_elem.findall(".//MeshHeading/DescriptorName"):
        if mesh.text:
            mesh_terms.append(mesh.text)
    if not mesh_terms:
        warnings.append("No MeSH terms (may not be indexed yet)")

    # Language
    lang_el = article_elem.find(".//Language")
    language = lang_el.text if lang_el is not None else ""
    if not language:
        warnings.append("Missing language")

    # DOI
    doi = None
    for id_el in article_elem.findall(".//ArticleId"):
        if id_el.get("IdType") == "doi":
            doi = id_el.text
            break
    if doi is None:
        warnings.append("No DOI")

    record = PubmedRecord(
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

    return record, warnings


def main():
    print("=" * 60)
    print("SPIKE 2: PubMed Search & Schema Mapping")
    print("=" * 60)
    print(f"Date range: {date_range}")
    print()

    # --- Test 1: Query volume comparison ---
    print("-" * 60)
    print("TEST 1: Query volume comparison")
    print("-" * 60)
    for name, query in QUERIES.items():
        pmids, total = esearch(query)
        print(f"  {name}: {total} total results (fetched {len(pmids)} IDs)")
        print(f"    Query: {query[:100]}...")
    print()

    # --- Test 2: Fetch and parse records ---
    print("-" * 60)
    print("TEST 2: Schema mapping — fetch 20 records from broad query")
    print("-" * 60)
    pmids, _ = esearch(QUERIES["broad_mesh"], retmax=20)
    if not pmids:
        print("  No results for this date range. Try widening the window.")
        sys.exit(1)

    xml_data = efetch(pmids)
    root = ET.fromstring(xml_data)
    articles = root.findall(".//PubmedArticle")
    print(f"  Fetched {len(articles)} articles\n")

    records = []
    all_warnings = {}
    field_coverage = {
        "pmid": 0, "title": 0, "authors": 0, "journal": 0,
        "abstract": 0, "pub_date": 0, "article_types": 0,
        "mesh_terms": 0, "language": 0, "doi": 0,
    }

    for article in articles:
        record, warnings = parse_record(article)
        if record is None:
            print(f"  SKIP: {warnings}")
            continue

        records.append(record)
        all_warnings[record.pmid] = warnings

        # Track field coverage
        if record.pmid: field_coverage["pmid"] += 1
        if record.title: field_coverage["title"] += 1
        if record.authors: field_coverage["authors"] += 1
        if record.journal: field_coverage["journal"] += 1
        if record.abstract: field_coverage["abstract"] += 1
        if record.pub_date: field_coverage["pub_date"] += 1
        if record.article_types: field_coverage["article_types"] += 1
        if record.mesh_terms: field_coverage["mesh_terms"] += 1
        if record.language: field_coverage["language"] += 1
        if record.doi: field_coverage["doi"] += 1

    # --- Test 3: Field coverage report ---
    print("-" * 60)
    print("TEST 3: Field coverage across all records")
    print("-" * 60)
    n = len(records)
    for field, count in field_coverage.items():
        pct = (count / n * 100) if n > 0 else 0
        status = "OK" if pct == 100 else ("WARN" if pct >= 80 else "ISSUE")
        print(f"  {field:20s}: {count}/{n} ({pct:.0f}%) [{status}]")
    print()

    # --- Test 4: Warning summary ---
    print("-" * 60)
    print("TEST 4: Warnings by type")
    print("-" * 60)
    warning_counts = {}
    for pmid, warns in all_warnings.items():
        for w in warns:
            warning_counts[w] = warning_counts.get(w, 0) + 1
    if warning_counts:
        for warning, count in sorted(warning_counts.items(), key=lambda x: -x[1]):
            print(f"  {count:3d}x  {warning}")
    else:
        print("  No warnings — all fields mapped cleanly!")
    print()

    # --- Test 5: Sample records ---
    print("-" * 60)
    print("TEST 5: Sample parsed records (first 3)")
    print("-" * 60)
    for record in records[:3]:
        print(f"\n  PMID: {record.pmid}")
        print(f"  Title: {record.title[:80]}{'...' if len(record.title) > 80 else ''}")
        print(f"  Authors: {', '.join(record.authors[:3])}{'...' if len(record.authors) > 3 else ''}")
        print(f"  Journal: {record.journal}")
        print(f"  Date: {record.pub_date}")
        print(f"  Types: {', '.join(record.article_types)}")
        print(f"  MeSH: {', '.join(record.mesh_terms[:5])}{'...' if len(record.mesh_terms) > 5 else ''}")
        print(f"  Language: {record.language}")
        print(f"  DOI: {record.doi or 'None'}")
        print(f"  Abstract: {record.abstract[:120]}{'...' if len(record.abstract) > 120 else ''}")
        print(f"  Warnings: {all_warnings.get(record.pmid, [])}")
    print()

    # --- Test 6: Abstract exclusion rate ---
    print("-" * 60)
    print("TEST 6: Pipeline exclusion preview")
    print("-" * 60)
    with_abstract = sum(1 for r in records if r.abstract)
    english = sum(1 for r in records if r.language == "eng")
    print(f"  Total parsed: {n}")
    print(f"  With abstract: {with_abstract} ({with_abstract/n*100:.0f}%)")
    print(f"  English: {english} ({english/n*100:.0f}%)")
    print(f"  Would pass basic filters (abstract + english): "
          f"{sum(1 for r in records if r.abstract and r.language == 'eng')}")
    print()

    # Save results
    output_path = os.path.join(os.path.dirname(__file__), "spike_results.json")
    with open(output_path, "w") as f:
        json.dump({
            "date_range": date_range,
            "query_volumes": {name: esearch(q)[1] for name, q in QUERIES.items()},
            "field_coverage": field_coverage,
            "warning_counts": warning_counts,
            "sample_records": [asdict(r) for r in records[:5]],
        }, f, indent=2)
    print(f"Results saved to {output_path}")

    # --- Spike verdict ---
    print()
    print("=" * 60)
    print("SPIKE VERDICT")
    print("=" * 60)
    issues = [f for f, c in field_coverage.items() if c / n < 0.8] if n > 0 else []
    if issues:
        print(f"  NEEDS ATTENTION: Fields with <80% coverage: {', '.join(issues)}")
        print("  Review the definition schema — some fields may need to be optional.")
    else:
        print("  ALL FIELDS map with >=80% coverage.")
        print("  Schema is viable. Proceed to spec.")


if __name__ == "__main__":
    main()
