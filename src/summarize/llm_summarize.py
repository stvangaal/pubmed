# owner: llm-summarize
"""LLM-powered summarization of filtered PubMed records.

Takes filtered PubmedRecord objects and produces LiteratureSummary objects
by calling the Anthropic API with a hybrid prompt template.
"""

import logging
from pathlib import Path

import anthropic

from src.models import LiteratureSummary, LLMUsage, PubmedRecord, SummaryConfig
from src.summarize.parse_summary import parse_summary

logger = logging.getLogger(__name__)


def summarize(
    records: list[PubmedRecord], config: SummaryConfig
) -> tuple[list[LiteratureSummary], LLMUsage]:
    """Summarize a list of filtered PubMed records using an LLM.

    For each record, formats a prompt, calls the Anthropic API, parses
    the structured response, and assembles a LiteratureSummary. Retries
    once on LLM failure; skips articles on parse failure.

    Args:
        records: PubmedRecord objects (should have status "filtered").
        config: SummaryConfig with prompt template, model, and other settings.

    Returns:
        Tuple of (summaries, llm_usage) where summaries is a list of
        LiteratureSummary objects and llm_usage tracks token counts.
    """
    prompt_template = _load_prompt_template(config)
    client = anthropic.Anthropic()
    summaries: list[LiteratureSummary] = []
    usage_tracker = LLMUsage(stage="Summarization", model=config.model)

    for record in records:
        summary = _summarize_one(
            record, config, prompt_template, client, usage_tracker
        )
        if summary is not None:
            summaries.append(summary)

    logger.info(
        "Summarized %d of %d records", len(summaries), len(records)
    )
    return summaries, usage_tracker


def _load_prompt_template(config: SummaryConfig) -> str:
    """Load the prompt template from config.prompt_template or a file.

    If config.prompt_template is set (non-empty), use it directly.
    Otherwise, read from the prompt_template_file path stored in the
    YAML config (not on SummaryConfig itself — the caller is expected
    to have loaded it into prompt_template before calling summarize).
    """
    if config.prompt_template:
        return config.prompt_template
    raise ValueError(
        "SummaryConfig.prompt_template is empty. Load the prompt template "
        "from config/prompts/summary-prompt.md into config.prompt_template "
        "before calling summarize()."
    )


def _summarize_one(
    record: PubmedRecord,
    config: SummaryConfig,
    prompt_template: str,
    client: anthropic.Anthropic,
    usage_tracker: LLMUsage | None = None,
) -> LiteratureSummary | None:
    """Summarize a single record. Returns None on failure."""
    formatted_prompt = _format_prompt(prompt_template, record, config)

    # Call LLM with one retry on failure
    raw_response = _call_llm(client, config, formatted_prompt, usage_tracker)
    if raw_response is None:
        logger.warning(
            "LLM call failed for PMID %s after retry — skipping", record.pmid
        )
        return None

    # Parse the structured response
    parsed = parse_summary(raw_response, config.subdomain_options)
    if parsed is None:
        logger.warning(
            "Parse failure for PMID %s — skipping. Raw response: %s",
            record.pmid,
            raw_response[:300],
        )
        return None

    # Build the feedback URL
    feedback_url = _build_feedback_url(config, record.pmid)

    return LiteratureSummary(
        pmid=record.pmid,
        title=record.title,
        journal=record.journal,
        pub_date=record.pub_date,
        subdomain=parsed["subdomain"],
        citation=parsed["citation"],
        research_question=parsed["research_question"],
        key_finding=parsed["key_finding"],
        design=parsed["design"],
        primary_outcome=parsed["primary_outcome"],
        limitations=parsed["limitations"],
        summary_short=parsed["summary_short"],
        triage_score=record.triage_score,
        triage_rationale=record.triage_rationale,
        feedback_url=feedback_url,
        raw_llm_response=raw_response,
        source_topic=record.source_topic,
        preindex=record.preindex,
        article_types=record.article_types,
    )


def _format_prompt(
    template: str, record: PubmedRecord, config: SummaryConfig
) -> str:
    """Insert record fields into the prompt template.

    Authors are formatted as first 3 names + 'et al.' when there are more.
    Subdomain options are joined into a comma-separated string.
    """
    authors_str = ", ".join(record.authors[:3])
    if len(record.authors) > 3:
        authors_str += " et al."

    return template.format(
        title=record.title,
        journal=record.journal,
        authors=authors_str,
        pmid=record.pmid,
        article_types=", ".join(record.article_types),
        abstract=record.abstract,
        subdomain_options=", ".join(config.subdomain_options),
    )


def _call_llm(
    client: anthropic.Anthropic,
    config: SummaryConfig,
    prompt: str,
    usage_tracker: LLMUsage | None = None,
) -> str | None:
    """Call the Anthropic API. Retry once on failure.

    Returns the text response, or None if both attempts fail.
    """
    for attempt in range(2):
        try:
            response = client.messages.create(
                model=config.model,
                max_tokens=config.max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            if usage_tracker:
                usage_tracker.add_response(response.usage)
            return response.content[0].text
        except Exception:
            if attempt == 0:
                logger.warning(
                    "LLM call failed (attempt 1), retrying...", exc_info=True
                )
            else:
                logger.error(
                    "LLM call failed (attempt 2), giving up.", exc_info=True
                )
    return None


def _build_feedback_url(config: SummaryConfig, pmid: str) -> str:
    """Construct the per-article feedback URL from config and PMID.

    Format: {feedback_form_url}?{feedback_pmid_field}={pmid}
    """
    if not config.feedback_form_url or not config.feedback_pmid_field:
        return ""
    return (
        f"{config.feedback_form_url}?{config.feedback_pmid_field}={pmid}"
    )
