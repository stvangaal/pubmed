# owner: spike (not governed — exploratory)
"""
Spike 1: Summarization Quality
Tests 3 prompt variations against real PubMed stroke abstracts.
Goal: Determine which prompt structure produces clinically useful summaries.
"""

import json
import xml.etree.ElementTree as ET
import subprocess
import sys
import os


def parse_articles(xml_path):
    """Parse PubMed XML into article dicts."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    articles = []

    for article in root.findall(".//PubmedArticle"):
        pmid = article.find(".//PMID").text

        title_el = article.find(".//ArticleTitle")
        title = "".join(title_el.itertext()) if title_el is not None else "No title"

        journal_el = article.find(".//Journal/Title")
        journal = journal_el.text if journal_el is not None else "Unknown"

        abstract_parts = article.findall(".//AbstractText")
        if abstract_parts:
            abstract = " ".join("".join(p.itertext()) for p in abstract_parts)
        else:
            abstract = ""

        pub_types = [pt.text for pt in article.findall(".//PublicationType") if pt.text]

        # Get authors
        authors = []
        for author in article.findall(".//Author"):
            last = author.find("LastName")
            first = author.find("ForeName")
            if last is not None:
                name = last.text
                if first is not None:
                    name = f"{last.text} {first.text[0]}"
                authors.append(name)

        if abstract:  # Only include articles with abstracts
            articles.append({
                "pmid": pmid,
                "title": title,
                "journal": journal,
                "authors": ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else ""),
                "abstract": abstract,
                "pub_types": pub_types,
            })

    return articles


# --- Prompt Variations ---

PROMPT_STRUCTURED = """You are a stroke medicine specialist summarizing publications for clinical colleagues.

Given a PubMed article about stroke, produce a structured summary with these exact sections:

**Objective:** What question did this study address? (1 sentence)
**Design:** Study type, population size, setting. (1 sentence)
**Key Finding:** The primary result, with numbers if available. (1-2 sentences)
**Clinical Relevance:** Why should a stroke clinician care? Could this change practice? (1-2 sentences)
**Limitations:** The most important caveat. (1 sentence)

Be specific. Use numbers from the abstract. Do not hedge excessively — state what the study found.

Article:
Title: {title}
Journal: {journal}
Authors: {authors}
Type: {pub_types}
Abstract: {abstract}
"""

PROMPT_NARRATIVE = """You are a stroke medicine specialist writing a brief for clinical colleagues.

Given a PubMed article about stroke, write a 3-4 sentence narrative summary. The summary should:
- Open with what the study investigated and why it matters
- State the key finding with specific numbers
- Close with what this means for clinical practice

Write in plain clinical English. No bullet points. No section headers. Be direct — clinicians are busy.

Article:
Title: {title}
Journal: {journal}
Authors: {authors}
Type: {pub_types}
Abstract: {abstract}
"""

PROMPT_HYBRID = """You are a stroke medicine specialist summarizing publications for clinical colleagues.

Given a PubMed article about stroke, produce a summary that follows this template EXACTLY. Do not add prefixes, labels, or brackets beyond what is shown.

---BEGIN TEMPLATE---
**Subdomain**
Article title. *Journal name*. [PMID](https://pubmed.ncbi.nlm.nih.gov/PMID/)

**Research Question:** One sentence framing the specific clinical question.

One sentence stating the key finding and its clinical implication. This is the only thing a busy clinician reads. Make it count.

**Details:**
- Design: study type, N, population
- Primary outcome: result with numbers
- Limitations: the most important methodological caveat affecting how much weight to give this finding
---END TEMPLATE---

Rules:
- Subdomain must be exactly one of: Acute Treatment, Prevention, Rehabilitation, Hospital Care, Imaging, Epidemiology
- Do NOT wrap the subdomain in brackets
- Citation format: Article title. *Journal name*. [PMID number](full URL)
- Be specific. Use numbers from the abstract. No filler.

Article:
Title: {title}
Journal: {journal}
Authors: {authors}
PMID: {pmid}
Type: {pub_types}
Abstract: {abstract}
"""

PROMPTS = {
    "hybrid": PROMPT_HYBRID,
}


def call_llm(prompt, article):
    """Call Claude API via the `claude` CLI's API, falling back to direct API call."""
    formatted = prompt.format(**article)

    # Use Anthropic API via Python
    try:
        import anthropic
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{"role": "user", "content": formatted}],
        )
        return response.content[0].text
    except ImportError:
        print("  [!] anthropic package not installed. Install with: pip install anthropic")
        print("  [!] Also set ANTHROPIC_API_KEY environment variable.")
        sys.exit(1)


def main():
    xml_path = "/tmp/pubmed_stroke_results.xml"

    if not os.path.exists(xml_path):
        print("No PubMed XML found. Run the fetch step first.")
        sys.exit(1)

    articles = parse_articles(xml_path)
    print(f"Parsed {len(articles)} articles with abstracts\n")

    # Use first 5 articles
    test_articles = articles[:5]

    results = {}

    for style_name, prompt_template in PROMPTS.items():
        print(f"\n{'='*60}")
        print(f"PROMPT STYLE: {style_name.upper()}")
        print(f"{'='*60}")

        results[style_name] = []

        for article in test_articles:
            print(f"\n--- PMID {article['pmid']}: {article['title'][:80]}... ---\n")
            summary = call_llm(prompt_template, article)
            print(summary)
            print()
            results[style_name].append({
                "pmid": article["pmid"],
                "title": article["title"],
                "summary": summary,
            })

    # Save results for comparison
    output_path = os.path.join(os.path.dirname(__file__), "spike_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Results saved to {output_path}")
    print(f"Compare the 3 styles and pick the one that best serves your audience.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
