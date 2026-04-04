# owner: ai-evaluation
"""Post-run summary completeness checks.

Validates structural integrity of LLM-generated summaries: field presence,
sentence count, tag validity, citation URL format.  Zero LLM cost.

Usage:
    python -m tests.eval.summary_completeness --summaries output/summaries.json
"""

import argparse
import json
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Fields that must be present and non-empty on every LiteratureSummary
REQUIRED_FIELDS = [
    "tags",
    "citation",
    "research_question",
    "key_finding",
    "design",
    "primary_outcome",
    "limitations",
    "summary_short",
]

PUBMED_URL_PATTERN = re.compile(r"https://pubmed\.ncbi\.nlm\.nih\.gov/\d+")


@dataclass
class CompletenessResult:
    """Result of completeness checks for a single summary."""

    pmid: str
    fields_present: int
    fields_total: int
    short_summary_sentences: int
    has_valid_citation_url: bool
    has_valid_tags: bool
    issues: list[str]

    @property
    def is_complete(self) -> bool:
        return len(self.issues) == 0


def check_summary(summary: dict, valid_tags: list[str] | None = None) -> CompletenessResult:
    """Check a single summary for structural completeness.

    Args:
        summary: Dictionary with LiteratureSummary fields.
        valid_tags: Optional list of valid subdomain tags.

    Returns:
        CompletenessResult with details.
    """
    issues: list[str] = []
    fields_present = 0

    for field_name in REQUIRED_FIELDS:
        value = summary.get(field_name)
        if value and (not isinstance(value, list) or len(value) > 0):
            fields_present += 1
        else:
            issues.append(f"missing or empty: {field_name}")

    # Short summary sentence count
    short_summary = summary.get("summary_short", "")
    sentences = [s.strip() for s in re.split(r'[.!?]+', short_summary) if s.strip()]
    sentence_count = len(sentences)
    if sentence_count != 2:
        issues.append(f"short_summary has {sentence_count} sentences (expected 2)")

    # Citation URL
    citation = summary.get("citation", "")
    has_valid_url = bool(PUBMED_URL_PATTERN.search(citation))
    if not has_valid_url:
        issues.append("citation missing valid PubMed URL")

    # Tag validity
    tags = summary.get("tags", [])
    has_valid_tags = True
    if valid_tags and tags:
        lower_valid = {t.lower() for t in valid_tags}
        invalid = [t for t in tags if t.lower() not in lower_valid]
        if invalid:
            has_valid_tags = False
            issues.append(f"invalid tags: {invalid}")

    return CompletenessResult(
        pmid=summary.get("pmid", "unknown"),
        fields_present=fields_present,
        fields_total=len(REQUIRED_FIELDS),
        short_summary_sentences=sentence_count,
        has_valid_citation_url=has_valid_url,
        has_valid_tags=has_valid_tags,
        issues=issues,
    )


def check_batch(
    summaries: list[dict], valid_tags: list[str] | None = None
) -> dict:
    """Check a batch of summaries and return aggregate statistics.

    Returns:
        Dictionary with aggregate completeness metrics.
    """
    results = [check_summary(s, valid_tags) for s in summaries]
    total = len(results)
    if total == 0:
        return {"total": 0, "complete": 0, "rate": 0.0, "issues": []}

    complete = sum(1 for r in results if r.is_complete)
    all_issues = []
    for r in results:
        for issue in r.issues:
            all_issues.append({"pmid": r.pmid, "issue": issue})

    return {
        "total": total,
        "complete": complete,
        "rate": round(complete / total, 3),
        "field_presence_rate": round(
            sum(r.fields_present for r in results) / (total * len(REQUIRED_FIELDS)), 3
        ),
        "two_sentence_rate": round(
            sum(1 for r in results if r.short_summary_sentences == 2) / total, 3
        ),
        "valid_citation_rate": round(
            sum(1 for r in results if r.has_valid_citation_url) / total, 3
        ),
        "valid_tag_rate": round(
            sum(1 for r in results if r.has_valid_tags) / total, 3
        ),
        "issues": all_issues,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Check summary completeness"
    )
    parser.add_argument("--summaries", required=True, help="Path to summaries JSON")
    parser.add_argument("--tags", default="", help="Comma-separated valid tags")
    args = parser.parse_args()

    with open(args.summaries) as f:
        summaries = json.load(f)

    valid_tags = [t.strip() for t in args.tags.split(",") if t.strip()] or None
    result = check_batch(summaries, valid_tags)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
