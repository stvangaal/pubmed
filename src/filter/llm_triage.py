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

from src.models import LLMTriageConfig, LLMUsage, PubmedRecord

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
    topic_prompts: dict[str, str] | None = None,
    readonly_seen_pmids: bool = False,
) -> tuple[list[PubmedRecord], list[PubmedRecord], LLMUsage]:
    """Score records with an LLM and split by threshold.

    Args:
        records: PubmedRecord objects post-rule-filter (status "retrieved").
        config: LLMTriageConfig with model, threshold, caching settings.
        output_dir: Optional directory for below-threshold log and merged
            exclusion log.
        seen_pmids_path: Path to seen-pmids.json for cross-run dedup.
        topic_prompts: Optional mapping of topic name → prompt file path.
            When a record's source_topic has an entry here, that prompt is
            used instead of the default triage prompt.
        readonly_seen_pmids: When True, read seen-pmids for dedup but do
            not write back. Used in test mode to avoid polluting the file.

    Returns:
        Tuple of (above_threshold, below_threshold, llm_usage) where the
        first two are lists sorted by triage_score descending (above_threshold
        capped at config.max_articles) and llm_usage tracks token counts.
    """
    topic_prompts = topic_prompts or {}

    # --- Dedup: skip PMIDs already scored in prior runs ---
    seen_pmids = _load_seen_pmids(seen_pmids_path)
    new_records = [r for r in records if r.pmid not in seen_pmids]
    skipped = len(records) - len(new_records)
    if skipped:
        logger.info("Dedup: skipped %d previously seen PMIDs", skipped)

    # --- Load and cache system prompts per topic ---
    default_prompt = _load_system_prompt(config.triage_prompt_file)
    prompt_cache: dict[str, str] = {"": default_prompt}
    for topic_name, prompt_file in topic_prompts.items():
        prompt_cache[topic_name] = _load_system_prompt(prompt_file)

    # --- Group records by prompt to maximize prompt caching ---
    def _prompt_key(r: PubmedRecord) -> str:
        return r.source_topic if r.source_topic in prompt_cache else ""

    # --- Build system messages per prompt key ---
    system_messages: dict[str, object] = {}
    for key, prompt_text in prompt_cache.items():
        if config.use_prompt_caching:
            system_messages[key] = [
                {
                    "type": "text",
                    "text": prompt_text,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system_messages[key] = prompt_text

    # --- Score each record ---
    client = anthropic.Anthropic()
    scored: list[PubmedRecord] = []
    usage_tracker = LLMUsage(stage="LLM Triage", model=config.model)

    # Sort by prompt key so records sharing a prompt are scored consecutively
    # (maximizes prompt caching effectiveness)
    sorted_records = sorted(new_records, key=_prompt_key)

    for record in sorted_records:
        key = _prompt_key(record)
        system_message = system_messages[key]
        user_content = _build_user_message(record)
        score, rationale = _call_llm(
            client, config, system_message, user_content, usage_tracker
        )
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

    # Backfill to meet min_articles guarantee
    if config.min_articles > 0 and len(above_threshold) < config.min_articles:
        need = config.min_articles - len(above_threshold)
        eligible = [
            r
            for r in below_threshold
            if (r.triage_score or 0.0) >= config.min_score_floor
        ]
        backfill = eligible[:need]  # already sorted by score desc
        backfill_pmids = {r.pmid for r in backfill}
        for r in backfill:
            r.triage_rationale = (
                f"[Backfilled to meet {config.min_articles}-article minimum] "
                f"{r.triage_rationale}"
            )
        above_threshold.extend(backfill)
        above_threshold.sort(key=lambda r: r.triage_score or 0.0, reverse=True)
        below_threshold = [
            r for r in below_threshold if r.pmid not in backfill_pmids
        ]
        if backfill:
            logger.info(
                "Backfilled %d articles (min_articles=%d, lowest=%.2f)",
                len(backfill),
                config.min_articles,
                min(r.triage_score or 0.0 for r in backfill),
            )

    # --- Update seen-PMIDs ---
    if not readonly_seen_pmids:
        new_pmids = {r.pmid for r in scored}
        _save_seen_pmids(seen_pmids | new_pmids, seen_pmids_path)

    # --- Write output logs ---
    if output_dir is not None:
        _write_below_threshold_log(below_threshold, output_dir)
        _append_triage_exclusions(below_threshold, output_dir)

    return above_threshold, below_threshold, usage_tracker


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
    usage_tracker: LLMUsage | None = None,
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
    raw_text = _call_with_retry(client, kwargs, usage_tracker)

    # Parse the JSON response
    return _parse_response(raw_text)


def _call_with_retry(
    client: anthropic.Anthropic,
    kwargs: dict,
    usage_tracker: LLMUsage | None = None,
) -> str:
    """Call client.messages.create; retry once on failure."""
    try:
        response = client.messages.create(**kwargs)
        if usage_tracker:
            usage_tracker.add_response(response.usage)
        return response.content[0].text.strip()
    except Exception as e:
        logger.warning("LLM call failed, retrying once: %s", e)
        try:
            response = client.messages.create(**kwargs)
            if usage_tracker:
                usage_tracker.add_response(response.usage)
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
