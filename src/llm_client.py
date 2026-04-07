# owner: project-infrastructure
"""Shared Anthropic LLM client helpers.

Provides a retry-once wrapper for Anthropic API calls, used by both
the triage and summarization stages.
"""

import logging

import anthropic

from src.models import LLMUsage

logger = logging.getLogger(__name__)


def call_llm_with_retry(
    client: anthropic.Anthropic,
    kwargs: dict,
    usage_tracker: LLMUsage | None = None,
) -> str | None:
    """Call client.messages.create with a single retry on failure.

    Args:
        client: Anthropic client instance.
        kwargs: Keyword arguments passed to client.messages.create.
        usage_tracker: Optional LLMUsage to accumulate token counts.

    Returns:
        The text content of the first response block (stripped), or None
        if both attempts fail.
    """
    for attempt in range(2):
        try:
            response = client.messages.create(**kwargs)
            if usage_tracker:
                usage_tracker.add_response(response.usage)
            return response.content[0].text.strip()
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
