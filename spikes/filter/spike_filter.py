# owner: spike (not governed — exploratory)
"""
Spike 3: Filter Calibration
Searches 6 weeks of PubMed stroke literature, applies rule-based
filtering then LLM triage, and presents the top 10 per week for
manual review of the cutoff.

Questions:
1. How many articles survive the rule-based filter per week?
2. Can the LLM triage reliably score clinical relevance?
3. Where should the cutoff sit to hit ~5 articles/week?
4. What gets missed just below the cutoff?
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


# --- Rule-based filter config ---

INCLUDE_TYPES = {
    "randomized controlled trial",
    "meta-analysis",
    "systematic review",
    "practice guideline",
    "guideline",
    "clinical trial",
    "clinical trial, phase iii",
    "clinical trial, phase iv",
    "multicenter study",
    "observational study",
    "comparative study",
}

EXCLUDE_TYPES = {
    "case reports",
    "letter",
    "editorial",
    "comment",
    "news",
    "biography",
    "historical article",
    "published erratum",
    "retraction of publication",
    "retracted publication",
}

EXCLUDE_MESH = {
    "animals",
    "mice",
    "rats",
    "disease models, animal",
    "in vitro techniques",
}

PRIORITY_JOURNALS = {
    "the new england journal of medicine",
    "the lancet",
    "the lancet. neurology",
    "jama",
    "jama neurology",
    "stroke",
    "annals of neurology",
    "neurology",
    "circulation",
    "bmj (clinical research ed.)",
    "annals of internal medicine",
    "european stroke journal",
    "international journal of stroke",
}

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _rate_limit():
    time.sleep(0.4)


def esearch(query, retmax=200):
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
    """Parse a PubmedArticle XML element into a PubmedRecord."""
    pmid_el = article_elem.find(".//PMID")
    pmid = pmid_el.text if pmid_el is not None else None
    if not pmid:
        return None

    title_el = article_elem.find(".//ArticleTitle")
    title = "".join(title_el.itertext()) if title_el is not None else ""

    authors = []
    for author in article_elem.findall(".//Author"):
        last = author.find("LastName")
        first = author.find("ForeName")
        if last is not None and last.text:
            name = last.text
            if first is not None and first.text:
                name = f"{last.text} {first.text[0]}"
            authors.append(name)

    journal_el = article_elem.find(".//Journal/Title")
    journal = journal_el.text if journal_el is not None else ""

    abstract_parts = article_elem.findall(".//AbstractText")
    abstract = " ".join("".join(p.itertext()) for p in abstract_parts) if abstract_parts else ""

    # Date normalization
    pub_date = ""
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
    if not pub_date:
        date_el = article_elem.find(".//PubDate")
        if date_el is not None:
            y = date_el.find("Year")
            m = date_el.find("Month")
            if y is not None and y.text:
                pub_date = y.text
                if m is not None and m.text:
                    pub_date += f"-{m.text}"

    article_types = [pt.text for pt in article_elem.findall(".//PublicationType") if pt.text]
    mesh_terms = [m.text for m in article_elem.findall(".//MeshHeading/DescriptorName") if m.text]
    lang_el = article_elem.find(".//Language")
    language = lang_el.text if lang_el is not None else ""

    doi = None
    for id_el in article_elem.findall(".//ArticleId"):
        if id_el.get("IdType") == "doi":
            doi = id_el.text
            break

    return PubmedRecord(
        pmid=pmid, title=title, authors=authors, journal=journal,
        abstract=abstract, pub_date=pub_date, article_types=article_types,
        mesh_terms=mesh_terms, language=language, doi=doi,
        status="retrieved", triage_score=None, triage_rationale=None,
    )


def rule_filter(records):
    """
    Apply rule-based filtering. Returns (passed, excluded_with_reasons).
    """
    passed = []
    excluded = []

    for r in records:
        # Must have abstract
        if not r.abstract:
            excluded.append((r, "no abstract"))
            continue

        # Must be English
        if r.language != "eng":
            excluded.append((r, f"language: {r.language}"))
            continue

        # Exclude animal studies by MeSH
        mesh_lower = {m.lower() for m in r.mesh_terms}
        animal_match = mesh_lower & EXCLUDE_MESH
        if animal_match and "humans" not in mesh_lower:
            excluded.append((r, f"animal study: {animal_match}"))
            continue

        # Check article types
        types_lower = {t.lower() for t in r.article_types}

        # Exclude unwanted types
        exclude_match = types_lower & EXCLUDE_TYPES
        if exclude_match and not (types_lower & INCLUDE_TYPES):
            excluded.append((r, f"excluded type: {exclude_match}"))
            continue

        passed.append(r)

    return passed, excluded


TRIAGE_PROMPT = """You are a stroke medicine specialist evaluating articles for a weekly clinical digest.

Score this article's relevance to practicing stroke clinicians on a scale of 0.0 to 1.0:

- 0.9-1.0: Definitely practice-changing — new RCT, guideline, or meta-analysis that should alter clinical decisions in acute stroke, stroke prevention, rehabilitation, or hospital care
- 0.7-0.8: Highly relevant — strong clinical evidence that informs but may not immediately change practice
- 0.5-0.6: Moderately relevant — useful clinical knowledge but incremental or narrow scope
- 0.3-0.4: Low relevance — basic science with clinical implications, small pilot studies, or tangential to stroke care
- 0.0-0.2: Not relevant — basic science only, non-clinical, or not actionable for stroke clinicians

Consider:
- Study design strength (RCT > cohort > case series)
- Sample size and statistical power
- Clinical actionability (could this change what a clinician does tomorrow?)
- Journal reputation in stroke/neurology/general medicine
- Novelty (first of its kind vs. confirmatory)

Respond with ONLY a JSON object, no other text:
{{"score": <float>, "rationale": "<one sentence explanation>"}}

Article:
Title: {title}
Journal: {journal}
Type: {article_types}
MeSH: {mesh_terms}
Abstract: {abstract}
"""


def llm_triage(records):
    """Score articles using LLM. Returns records with triage_score and triage_rationale set."""
    import anthropic
    client = anthropic.Anthropic()

    scored = []
    for i, r in enumerate(records):
        prompt = TRIAGE_PROMPT.format(
            title=r.title,
            journal=r.journal,
            article_types=", ".join(r.article_types),
            mesh_terms=", ".join(r.mesh_terms[:10]),
            abstract=r.abstract[:2000],  # Truncate very long abstracts
        )

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=150,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()

            # Parse JSON response
            result = json.loads(text)
            r.triage_score = float(result["score"])
            r.triage_rationale = result["rationale"]
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"    [!] Parse error for PMID {r.pmid}: {e}")
            print(f"        Raw response: {text[:200]}")
            r.triage_score = 0.0
            r.triage_rationale = f"Parse error: {e}"
        except Exception as e:
            print(f"    [!] LLM error for PMID {r.pmid}: {e}")
            r.triage_score = 0.0
            r.triage_rationale = f"LLM error: {e}"

        r.status = "filtered"
        scored.append(r)

        # Progress indicator
        if (i + 1) % 5 == 0:
            print(f"    Scored {i + 1}/{len(records)}...")

    return scored


def get_week_ranges(num_weeks=6):
    """Generate date ranges for the past N weeks."""
    today = datetime.now()
    weeks = []
    for i in range(num_weeks):
        end = today - timedelta(weeks=i)
        start = end - timedelta(days=7)
        weeks.append((
            start.strftime("%Y/%m/%d"),
            end.strftime("%Y/%m/%d"),
            f"Week {i + 1} ({start.strftime('%b %d')} - {end.strftime('%b %d')})",
        ))
    return weeks


def main():
    print("=" * 70)
    print("SPIKE 3: Filter Calibration — 6 Weeks of Stroke Literature")
    print("=" * 70)
    print()

    weeks = get_week_ranges(6)
    all_results = {}

    for start_date, end_date, label in weeks:
        print(f"\n{'='*70}")
        print(f"{label}")
        print(f"{'='*70}")

        # Search
        query = f'"stroke"[MeSH Major Topic] AND {start_date}:{end_date}[Date - Entry]'
        pmids, total = esearch(query)
        print(f"  Search: {total} total articles")

        if not pmids:
            print("  No results this week.")
            all_results[label] = {"total": 0, "rule_passed": 0, "top_10": []}
            continue

        # Fetch
        xml_data = efetch(pmids)
        root = ET.fromstring(xml_data)
        articles = root.findall(".//PubmedArticle")
        records = [r for r in (parse_record(a) for a in articles) if r is not None]
        print(f"  Parsed: {len(records)} records")

        # Rule filter
        passed, excluded = rule_filter(records)
        print(f"  Rule filter: {len(passed)} passed, {len(excluded)} excluded")

        # Exclusion breakdown
        reasons = {}
        for _, reason in excluded:
            reasons[reason] = reasons.get(reason, 0) + 1
        if reasons:
            for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
                print(f"    - {count}x {reason}")

        if not passed:
            print("  No articles passed rule filter.")
            all_results[label] = {"total": total, "rule_passed": 0, "top_10": []}
            continue

        # LLM triage
        print(f"  LLM triage: scoring {len(passed)} articles...")
        scored = llm_triage(passed)

        # Sort by score descending
        scored.sort(key=lambda r: r.triage_score or 0, reverse=True)

        # Show top 10
        top_10 = scored[:10]
        print(f"\n  {'─'*66}")
        print(f"  TOP 10 (target cutoff: top 5)")
        print(f"  {'─'*66}")

        for i, r in enumerate(top_10):
            marker = ">>>" if i < 5 else "   "
            in_priority = r.journal.lower() in PRIORITY_JOURNALS
            journal_flag = " *" if in_priority else ""

            print(f"  {marker} {i+1:2d}. [{r.triage_score:.2f}] PMID {r.pmid}")
            print(f"       {r.title[:90]}{'...' if len(r.title) > 90 else ''}")
            print(f"       {r.journal}{journal_flag} | {', '.join(r.article_types[:2])}")
            print(f"       {r.triage_rationale}")
            print()

        # Stats
        if len(scored) >= 5:
            cutoff_score = scored[4].triage_score
            print(f"  Cutoff at position 5: score = {cutoff_score:.2f}")
            if len(scored) >= 6:
                gap = scored[4].triage_score - scored[5].triage_score
                print(f"  Gap between #5 and #6: {gap:.2f}")

        all_results[label] = {
            "total": total,
            "rule_passed": len(passed),
            "scored": len(scored),
            "top_10": [
                {
                    "rank": i + 1,
                    "pmid": r.pmid,
                    "title": r.title,
                    "journal": r.journal,
                    "score": r.triage_score,
                    "rationale": r.triage_rationale,
                    "article_types": r.article_types,
                }
                for i, r in enumerate(top_10)
            ],
        }

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY ACROSS 6 WEEKS")
    print(f"{'='*70}")
    print(f"  {'Week':<35} {'Total':>6} {'Rule':>6} {'Scored':>7}")
    print(f"  {'─'*55}")
    for label, data in all_results.items():
        print(f"  {label:<35} {data['total']:>6} {data['rule_passed']:>6} {data.get('scored', 0):>7}")

    # Save results
    output_path = os.path.join(os.path.dirname(__file__), "spike_results.json")
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
