# owner: rule-filter
"""Deterministic rule-based filter for PubMed records.

Applies cost-free filtering before LLM triage: removes articles without
abstracts, non-English articles, animal studies (via MeSH), and excluded
article types.  Include types take precedence over exclude types.
"""

import json
import os
from dataclasses import asdict

from src.models import PubmedRecord, RuleFilterConfig


def rule_filter(
    records: list[PubmedRecord],
    config: RuleFilterConfig,
    output_dir: str | None = None,
) -> tuple[list[PubmedRecord], list[tuple[PubmedRecord, str]]]:
    """Apply deterministic filters and return (passed, excluded) lists.

    Filters are applied in order (short-circuit on first exclusion):
      1. Abstract check
      2. Language check
      3. Animal study check (MeSH)
      4. Article type check

    Args:
        records: PubmedRecord objects with status "retrieved".
        config: RuleFilterConfig with filter parameters.
        output_dir: Optional directory to write filter-exclusions.json.

    Returns:
        Tuple of (passed, excluded) where excluded items are
        (PubmedRecord, reason) tuples.
    """
    # Pre-compute lower-cased sets for case-insensitive comparison
    include_types = {t.lower() for t in config.include_article_types}
    exclude_types = {t.lower() for t in config.exclude_article_types}
    exclude_mesh = {t.lower() for t in config.exclude_mesh_terms}
    require_lang = config.require_language.lower()

    passed: list[PubmedRecord] = []
    excluded: list[tuple[PubmedRecord, str]] = []

    for record in records:
        # 1. Abstract check
        if config.require_abstract and not record.abstract:
            excluded.append((record, "no abstract"))
            continue

        # 2. Language check
        if record.language.lower() != require_lang:
            excluded.append((record, f"language: {record.language}"))
            continue

        # 3. Animal study check — exclude if any MeSH matches the exclude
        #    list AND "humans" is NOT present in the MeSH terms.
        mesh_lower = {m.lower() for m in record.mesh_terms}
        if (mesh_lower & exclude_mesh) and "humans" not in mesh_lower:
            excluded.append((record, "animal study"))
            continue

        # 4. Article type check — include types take precedence over
        #    exclude types (e.g. an RCT tagged as "Case Reports" passes).
        types_lower = {t.lower() for t in record.article_types}
        matched_excludes = types_lower & exclude_types
        if matched_excludes and not (types_lower & include_types):
            excluded.append(
                (record, f"excluded type: {sorted(matched_excludes)}")
            )
            continue

        passed.append(record)

    # Write exclusion log for troubleshooting
    if output_dir is not None:
        _write_exclusion_log(excluded, output_dir)

    return passed, excluded


def _write_exclusion_log(
    excluded: list[tuple[PubmedRecord, str]],
    output_dir: str,
) -> None:
    """Write machine-readable exclusion log to filter-exclusions.json."""
    os.makedirs(output_dir, exist_ok=True)
    log_path = os.path.join(output_dir, "filter-exclusions.json")

    entries = [
        {
            "pmid": record.pmid,
            "title": record.title,
            "journal": record.journal,
            "excluded_by": "rule_filter",
            "reason": reason,
        }
        for record, reason in excluded
    ]

    with open(log_path, "w") as f:
        json.dump(entries, f, indent=2)
