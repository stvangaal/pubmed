# owner: spike (not governed — exploratory)
"""
Spike 3b: Filter Calibration — Refined
Fixes from v1: model upgrade, review scoring, prompt caching, date boundaries.
Runs a single week to verify fixes before finalizing spec.
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


# --- Config (would be loaded from YAML in production) ---

FILTER_CONFIG = {
    "rule_filter": {
        "include_article_types": [
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
        ],
        "exclude_article_types": [
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
        ],
        "exclude_mesh_terms": [
            "animals",
            "mice",
            "rats",
            "disease models, animal",
            "in vitro techniques",
        ],
        "require_language": "eng",
        "require_abstract": True,
    },
    "llm_triage": {
        "model": "claude-sonnet-4-6",
        "max_tokens": 150,
        "score_threshold": 0.70,
        "max_articles": 10,
        "use_prompt_caching": True,
    },
    "priority_journals": [
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
    ],
}

# --- Triage prompt (expanded with examples for caching threshold) ---

TRIAGE_SYSTEM_PROMPT = """You are a stroke medicine specialist evaluating articles for a weekly clinical digest aimed at practicing stroke clinicians.

Your task: score each article's relevance on a scale of 0.00 to 1.00. Use the full range and avoid rounding to 0.1 increments — differentiate between articles within the same tier.

## Scoring Guide

0.90-1.00: Practice-changing. New RCT results, updated clinical guidelines, or definitive meta-analyses that should alter clinical decisions in acute stroke care, stroke prevention, rehabilitation, or hospital care.

0.80-0.89: Highly relevant. Strong clinical evidence that informs practice. Includes: large observational studies with actionable findings, phase 2 trials of promising interventions, authoritative clinical reviews from top-tier journals (Lancet, NEJM, JAMA, Lancet Neurology, Stroke, Neurology, BMJ) that synthesize current evidence for clinical audiences.

0.70-0.79: Clinically informative. Solid evidence that a stroke clinician would benefit from knowing: well-designed cohort studies, systematic reviews in subspecialty journals, novel diagnostic approaches with validation data.

0.50-0.69: Incremental. Useful but not urgent: small pilot studies, confirmatory findings, narrative reviews, prediction model development, single-center retrospective studies with modest sample sizes.

0.30-0.49: Low relevance. Basic science with distant clinical implications, methodological papers, tangential topics, studies in populations not generalizable to typical stroke care.

0.00-0.29: Not relevant. Basic science only, non-clinical, not actionable.

## Scoring Factors

- Study design strength: RCT > prospective cohort > retrospective > case series
- Sample size and statistical rigor
- Clinical actionability: could this change what a clinician does?
- Journal tier in stroke/neurology/general medicine
- Novelty vs. confirmatory

## Important

- Authoritative clinical reviews from top-tier journals ARE high-value for a clinical digest even without novel primary data. A comprehensive Lancet review on atrial fibrillation management that covers stroke prevention IS relevant to stroke clinicians (score 0.80+).
- Trial protocols without results are informative but not practice-changing (0.50-0.65).
- Geographic-specific epidemiology with limited generalizability should score lower.
- Use two decimal places to differentiate within tiers.

## Scoring Examples

Example 1: Large RCT in Lancet Neurology showing direct angio suite transfer increases hemorrhage risk
→ {"score": 0.93, "rationale": "Practice-changing RCT with clear safety signal affecting acute stroke workflows."}

Example 2: Cochrane systematic review of vagus nerve stimulation for post-stroke upper limb rehab
→ {"score": 0.82, "rationale": "High-quality evidence synthesis from Cochrane on emerging rehabilitation modality."}

Example 3: Comprehensive Lancet review on atrial fibrillation covering stroke prevention strategies
→ {"score": 0.81, "rationale": "Authoritative review from top-tier journal synthesizing current AF and stroke prevention evidence for clinical audiences."}

Example 4: Retrospective study (n=200) identifying risk factors for neurological deterioration in LVO stroke
→ {"score": 0.55, "rationale": "Small retrospective study with incremental findings on known risk factors."}

Example 5: Nomogram development for predicting outcomes, published in a lower-tier journal
→ {"score": 0.48, "rationale": "Prediction model development without external validation in a lower-impact journal."}

Respond with ONLY a JSON object:
{"score": <float two decimals>, "rationale": "<one sentence>"}"""

TRIAGE_USER_TEMPLATE = """Title: {title}
Journal: {journal}
Type: {article_types}
MeSH: {mesh_terms}
Abstract: {abstract}"""


BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _rate_limit():
    time.sleep(0.4)


def esearch(query, retmax=200):
    _rate_limit()
    params = urllib.parse.urlencode({
        "db": "pubmed", "term": query, "retmax": retmax, "retmode": "json",
    })
    url = f"{BASE_URL}/esearch.fcgi?{params}"
    with urllib.request.urlopen(url) as resp:
        data = json.loads(resp.read())
    result = data["esearchresult"]
    return result["idlist"], int(result["count"])


def efetch(pmids):
    _rate_limit()
    params = urllib.parse.urlencode({
        "db": "pubmed", "id": ",".join(pmids), "rettype": "xml", "retmode": "xml",
    })
    url = f"{BASE_URL}/efetch.fcgi?{params}"
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode("utf-8")


def parse_record(article_elem):
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

    pub_date = ""
    date_el = article_elem.find(".//ArticleDate")
    if date_el is not None:
        y, m, d = date_el.find("Year"), date_el.find("Month"), date_el.find("Day")
        if y is not None and y.text:
            pub_date = y.text
            if m is not None and m.text:
                pub_date += f"-{m.text.zfill(2)}"
                if d is not None and d.text:
                    pub_date += f"-{d.text.zfill(2)}"
    if not pub_date:
        date_el = article_elem.find(".//PubDate")
        if date_el is not None:
            y, m = date_el.find("Year"), date_el.find("Month")
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


def rule_filter(records, config):
    cfg = config["rule_filter"]
    include_types = {t.lower() for t in cfg["include_article_types"]}
    exclude_types = {t.lower() for t in cfg["exclude_article_types"]}
    exclude_mesh = {t.lower() for t in cfg["exclude_mesh_terms"]}

    passed, excluded = [], []
    for r in records:
        if cfg["require_abstract"] and not r.abstract:
            excluded.append((r, "no abstract")); continue
        if r.language != cfg["require_language"]:
            excluded.append((r, f"language: {r.language}")); continue
        mesh_lower = {m.lower() for m in r.mesh_terms}
        if (mesh_lower & exclude_mesh) and "humans" not in mesh_lower:
            excluded.append((r, "animal study")); continue
        types_lower = {t.lower() for t in r.article_types}
        if (types_lower & exclude_types) and not (types_lower & include_types):
            excluded.append((r, f"excluded type: {types_lower & exclude_types}")); continue
        passed.append(r)
    return passed, excluded


def llm_triage(records, config):
    import anthropic
    client = anthropic.Anthropic()
    cfg = config["llm_triage"]

    scored = []
    for i, r in enumerate(records):
        user_content = TRIAGE_USER_TEMPLATE.format(
            title=r.title,
            journal=r.journal,
            article_types=", ".join(r.article_types),
            mesh_terms=", ".join(r.mesh_terms[:10]),
            abstract=r.abstract[:2000],
        )

        kwargs = {
            "model": cfg["model"],
            "max_tokens": cfg["max_tokens"],
            "messages": [{"role": "user", "content": user_content}],
        }

        # Use prompt caching: system prompt as cached content block
        if cfg["use_prompt_caching"]:
            kwargs["system"] = [{
                "type": "text",
                "text": TRIAGE_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }]
        else:
            kwargs["system"] = TRIAGE_SYSTEM_PROMPT

        try:
            response = client.messages.create(**kwargs)
            text = response.content[0].text.strip()
            result = json.loads(text)
            r.triage_score = round(float(result["score"]), 2)
            r.triage_rationale = result["rationale"]

            # Report cache stats on first and every 10th call
            if i == 0 or (i + 1) % 10 == 0:
                usage = response.usage
                cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
                cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
                print(f"    [{i+1}] cache_write={cache_write}, cache_read={cache_read}, input={usage.input_tokens}")

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"    [!] Parse error PMID {r.pmid}: {e}")
            r.triage_score = 0.0
            r.triage_rationale = f"Parse error: {e}"
        except Exception as e:
            print(f"    [!] LLM error PMID {r.pmid}: {e}")
            r.triage_score = 0.0
            r.triage_rationale = f"LLM error: {e}"

        r.status = "filtered"
        scored.append(r)

        if (i + 1) % 5 == 0:
            print(f"    Scored {i + 1}/{len(records)}...")

    return scored


def main():
    print("=" * 70)
    print("SPIKE 3b: Filter Calibration — Refined (single week verification)")
    print("=" * 70)

    # Week 3 from v1 spike: Mar 02-09 — had the AF guideline miss
    # Fix: exclusive end date (subtract 1 day)
    start = "2026/03/02"
    end = "2026/03/08"  # exclusive: was 03/09 in v1, causing overlap
    query = f'"stroke"[MeSH Major Topic] AND {start}:{end}[Date - Entry]'

    print(f"\nDate range: {start} to {end} (exclusive end)")
    print(f"Query: {query}")

    # Search
    pmids, total = esearch(query)
    print(f"Search: {total} total articles")

    if not pmids:
        print("No results."); return

    # Fetch & parse
    xml_data = efetch(pmids)
    root = ET.fromstring(xml_data)
    records = [r for r in (parse_record(a) for a in root.findall(".//PubmedArticle")) if r]
    print(f"Parsed: {len(records)} records")

    # Rule filter
    passed, excluded = rule_filter(records, FILTER_CONFIG)
    print(f"Rule filter: {len(passed)} passed, {len(excluded)} excluded")

    # LLM triage
    print(f"LLM triage: scoring {len(passed)} articles with {FILTER_CONFIG['llm_triage']['model']}...")
    scored = llm_triage(passed, FILTER_CONFIG)
    scored.sort(key=lambda r: r.triage_score or 0, reverse=True)

    # Show all articles >= 0.50 to see the distribution
    threshold = FILTER_CONFIG["llm_triage"]["score_threshold"]
    above = [r for r in scored if (r.triage_score or 0) >= threshold]
    below = [r for r in scored if 0.50 <= (r.triage_score or 0) < threshold]

    print(f"\n{'─'*70}")
    print(f"ABOVE THRESHOLD (>= {threshold}) — {len(above)} articles")
    print(f"{'─'*70}")
    for i, r in enumerate(above):
        print(f"  {i+1:2d}. [{r.triage_score:.2f}] PMID {r.pmid}")
        print(f"      {r.title[:90]}")
        print(f"      {r.journal} | {', '.join(r.article_types[:2])}")
        print(f"      {r.triage_rationale}")
        print()

    print(f"{'─'*70}")
    print(f"BELOW THRESHOLD (0.50-{threshold}) — {len(below)} articles")
    print(f"{'─'*70}")
    for i, r in enumerate(below):
        print(f"  {i+1:2d}. [{r.triage_score:.2f}] PMID {r.pmid}")
        print(f"      {r.title[:90]}")
        print(f"      {r.journal} | {', '.join(r.article_types[:2])}")
        print(f"      {r.triage_rationale}")
        print()

    # Score distribution
    print(f"{'─'*70}")
    print("SCORE DISTRIBUTION")
    print(f"{'─'*70}")
    buckets = {"0.90+": 0, "0.80-0.89": 0, "0.70-0.79": 0, "0.60-0.69": 0, "0.50-0.59": 0, "<0.50": 0}
    for r in scored:
        s = r.triage_score or 0
        if s >= 0.90: buckets["0.90+"] += 1
        elif s >= 0.80: buckets["0.80-0.89"] += 1
        elif s >= 0.70: buckets["0.70-0.79"] += 1
        elif s >= 0.60: buckets["0.60-0.69"] += 1
        elif s >= 0.50: buckets["0.50-0.59"] += 1
        else: buckets["<0.50"] += 1
    for bucket, count in buckets.items():
        bar = "█" * count
        print(f"  {bucket:10s}: {count:3d} {bar}")

    # Save
    output_path = os.path.join(os.path.dirname(__file__), "spike_results_v2.json")
    with open(output_path, "w") as f:
        json.dump({
            "config": FILTER_CONFIG,
            "date_range": f"{start} to {end}",
            "total": total,
            "rule_passed": len(passed),
            "above_threshold": [{"pmid": r.pmid, "title": r.title, "journal": r.journal,
                                  "score": r.triage_score, "rationale": r.triage_rationale}
                                 for r in above],
            "below_threshold": [{"pmid": r.pmid, "title": r.title, "journal": r.journal,
                                  "score": r.triage_score, "rationale": r.triage_rationale}
                                 for r in below],
            "score_distribution": buckets,
        }, f, indent=2)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
