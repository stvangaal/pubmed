# owner: llm-triage
"""LLM-based triage scoring for rule-filtered PubMed records.

Scores each article for clinical relevance using an Anthropic LLM,
with prompt caching to reduce cost across a run.  Deduplicates against
previously seen PMIDs and writes scored results for auditing.
"""

import json
import logging
import os

import anthropic

from src.models import LLMTriageConfig, PubmedRecord

logger = logging.getLogger(__name__)

# Template for the per-article user message sent to the LLM.
_USER_TEMPLATE = """Title: {title}
Journal: {journal}
Type: {article_types}
MeSH: {mesh_terms}
Abstract: {abstract}"""

# Default path for the cross-run dedup file.
_SEEN_PMIDS_PATH = "data/seen-pmids.json"


def llm_triage(
    records: list[PubmedRecord],
    config: LLMTriageConfig,
    output_dir: str | None = None,
    seen_pmids_path: str = _SEEN_PMIDS_PATH,
) -> tuple[list[PubmedRecord], list[PubmedRecord]]:
    """Score records with an LLM and split by threshold.

    Args:
        records: PubmedRecord objects post-rule-filter (status "retrieved").
        config: LLMTriageConfig with model, threshold, caching settings.
        output_dir: Optional directory for below-threshold log and merged
            exclusion log.
        seen_pmids_path: Path to seen-pmids.json for cross-run dedup.

    Returns:
        Tuple of (above_threshold, below_threshold) lists, both sorted by
        triage_score descending.  above_threshold is capped at
        config.max_articles.
    """
    # --- Dedup: skip PMIDs already scored in prior runs ---
    seen_pmids = _load_seen_pmids(seen_pmids_path)
    new_records = [r for r in records if r.pmid not in seen_pmids]
    skipped = len(records) - len(new_records)
    if skipped:
        logger.info("Dedup: skipped %d previously seen PMIDs", skipped)

    # --- Load system prompt from file ---
    system_prompt = _load_system_prompt(config.triage_prompt_file)

    # --- Build the system message (with optional caching) ---
    if config.use_prompt_caching:
        system_message = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    else:
        system_message = system_prompt

    # --- Score each record ---
    client = anthropic.Anthropic()
    scored: list[PubmedRecord] = []

    for record in new_records:
        user_content = _build_user_message(record)
        score, rationale = _call_llm(client, config, system_message, user_content)
        record.triage_score = score
        record.triage_rationale = rationale
        record.status = "filtered"
        scored.append(record)

    # --- Split by threshold and cap ---
    scored.sort(key=lambda r: r.triage_score or 0.0, reverse=True)

    above_threshold = [
        r for r in scored if (r.triage_score or 0.0) >= config.score_threshold
    ]
    below_threshold = [
        r for r in scored if (r.triage_score or 0.0) < config.score_threshold
    ]

    # Cap at max_articles
    if len(above_threshold) > config.max_articles:
        # Move extras into below_threshold, re-sort
        extras = above_threshold[config.max_articles :]
        above_threshold = above_threshold[: config.max_articles]
        below_threshold = extras + below_threshold
        below_threshold.sort(key=lambda r: r.triage_score or 0.0, reverse=True)

    # --- Update seen-PMIDs ---
    new_pmids = {r.pmid for r in scored}
    _save_seen_pmids(seen_pmids | new_pmids, seen_pmids_path)

    # --- Write output logs ---
    if output_dir is not None:
        _write_below_threshold_log(below_threshold, output_dir)
        _append_triage_exclusions(below_threshold, output_dir)

    return above_threshold, below_threshold


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_system_prompt(prompt_file: str) -> str:
    """Read the triage system prompt from disk."""
    with open(prompt_file) as f:
        return f.read()


def _build_user_message(record: PubmedRecord) -> str:
    """Assemble the per-article user message from record fields."""
    return _USER_TEMPLATE.format(
        title=record.title,
        journal=record.journal,
        article_types=", ".join(record.article_types),
        mesh_terms=", ".join(record.mesh_terms[:10]),
        abstract=record.abstract[:2000],
    )


def _call_llm(
    client: anthropic.Anthropic,
    config: LLMTriageConfig,
    system_message,
    user_content: str,
) -> tuple[float, str]:
    """Call the LLM and parse the JSON response.

    Retries once on LLM failure.  Returns score 0.0 on parse failure.
    """
    kwargs = {
        "model": config.model,
        "max_tokens": config.max_tokens,
        "system": system_message,
        "messages": [{"role": "user", "content": user_content}],
    }

    # Attempt the call (with one retry on failure)
    raw_text = _call_with_retry(client, kwargs)

    # Parse the JSON response
    return _parse_response(raw_text)


def _call_with_retry(client: anthropic.Anthropic, kwargs: dict) -> str:
    """Call client.messages.create; retry once on failure."""
    try:
        response = client.messages.create(**kwargs)
        return response.content[0].text.strip()
    except Exception as e:
        logger.warning("LLM call failed, retrying once: %s", e)
        try:
            response = client.messages.create(**kwargs)
            return response.content[0].text.strip()
        except Exception as retry_err:
            logger.error("LLM retry failed: %s", retry_err)
            return ""


def _parse_response(raw_text: str) -> tuple[float, str]:
    """Extract score and rationale from the LLM JSON response.

    Returns (0.0, error_message) if parsing fails.
    """
    if not raw_text:
        return 0.0, "LLM call failed"

    try:
        result = json.loads(raw_text)
        score = round(float(result["score"]), 2)
        rationale = str(result["rationale"])
        return score, rationale
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        logger.warning("Parse error (raw=%r): %s", raw_text[:200], e)
        return 0.0, f"Parse error: {e}"


# ---------------------------------------------------------------------------
# Dedup helpers
# ---------------------------------------------------------------------------


def _load_seen_pmids(path: str) -> set[str]:
    """Load previously seen PMIDs from JSON file."""
    if not os.path.exists(path):
        return set()
    try:
        with open(path) as f:
            data = json.load(f)
        return set(data) if isinstance(data, list) else set()
    except (json.JSONDecodeError, OSError):
        return set()


def _save_seen_pmids(pmids: set[str], path: str) -> None:
    """Persist the full set of seen PMIDs to disk."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(sorted(pmids), f, indent=2)


# ---------------------------------------------------------------------------
# Output log helpers
# ---------------------------------------------------------------------------


def _write_below_threshold_log(
    below: list[PubmedRecord], output_dir: str
) -> None:
    """Write below-threshold articles to filter-triage-below-threshold.json."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "filter-triage-below-threshold.json")
    entries = [
        {
            "pmid": r.pmid,
            "title": r.title,
            "journal": r.journal,
            "score": r.triage_score,
            "rationale": r.triage_rationale,
        }
        for r in below
    ]
    with open(path, "w") as f:
        json.dump(entries, f, indent=2)


def _append_triage_exclusions(
    below: list[PubmedRecord], output_dir: str
) -> None:
    """Merge triage below-threshold entries into filter-exclusions.json.

    Reads any existing exclusion log (written by rule_filter) and appends
    triage entries so there's a single combined log per run.
    """
    os.makedirs(output_dir, exist_ok=True)
    log_path = os.path.join(output_dir, "filter-exclusions.json")

    # Load existing rule-filter entries if present
    existing: list[dict] = []
    if os.path.exists(log_path):
        try:
            with open(log_path) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    # Append triage entries
    for r in below:
        existing.append(
            {
                "pmid": r.pmid,
                "title": r.title,
                "journal": r.journal,
                "excluded_by": "llm_triage",
                "score": r.triage_score,
                "rationale": r.triage_rationale,
            }
        )

    with open(log_path, "w") as f:
        json.dump(existing, f, indent=2)
