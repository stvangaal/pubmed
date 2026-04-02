# owner: llm-summarize
"""Parse structured fields from an LLM-generated hybrid summary."""

import logging

logger = logging.getLogger(__name__)


def parse_summary(
    raw_response: str, subdomain_options: list[str]
) -> dict | None:
    """Extract structured fields from a hybrid-format LLM response.

    Uses simple string splitting on markdown delimiters (not regex).
    Returns a dict of parsed fields, or None if parsing fails.

    Expected format (from the hybrid prompt):
        **Subdomain**
        Citation line
        **Research Question:** ...
        Key finding paragraph
        **Details:**
        - Design: ...
        - Primary outcome: ...
        - Limitations: ...
        **Short Summary:** Two-sentence teaser.
    """
    try:
        lines = raw_response.strip().split("\n")

        # --- Tags: first non-empty line, comma-separated ---
        tags = _extract_tags(lines, subdomain_options)
        if tags is None:
            logger.warning(
                "Could not extract valid tags from response: %s",
                raw_response[:200],
            )
            return None

        # --- Citation: the line after the subdomain line ---
        citation = _extract_citation(lines)
        if citation is None:
            logger.warning(
                "Could not extract citation from response: %s",
                raw_response[:200],
            )
            return None

        # --- Research question ---
        research_question = _extract_after_marker(
            raw_response, "**Research Question:**"
        )
        if research_question is None:
            logger.warning(
                "Could not extract research question from response: %s",
                raw_response[:200],
            )
            return None

        # --- Key finding: text between Research Question and Details ---
        key_finding = _extract_key_finding(raw_response)
        if key_finding is None:
            logger.warning(
                "Could not extract key finding from response: %s",
                raw_response[:200],
            )
            return None

        # --- Details fields ---
        design = _extract_detail_field(raw_response, "- Design:")
        primary_outcome = _extract_detail_field(
            raw_response, "- Primary outcome:"
        )
        limitations = _extract_detail_field(raw_response, "- Limitations:")

        if any(v is None for v in [design, primary_outcome, limitations]):
            logger.warning(
                "Could not extract one or more detail fields from response: %s",
                raw_response[:200],
            )
            return None

        # --- Short summary ---
        summary_short = _extract_after_marker(
            raw_response, "**Short Summary:**"
        )
        if summary_short is None:
            logger.warning(
                "Could not extract short summary from response: %s",
                raw_response[:200],
            )
            return None

        return {
            "tags": tags,
            "citation": citation,
            "research_question": research_question,
            "key_finding": key_finding,
            "design": design,
            "primary_outcome": primary_outcome,
            "limitations": limitations,
            "summary_short": summary_short,
        }

    except Exception:
        logger.exception("Unexpected error parsing LLM response")
        return None


def _extract_tags(
    lines: list[str], subdomain_options: list[str]
) -> list[str] | None:
    """Extract one or more tags from the first non-empty line.

    Supports two formats:
    - New multi-tag: '**Tags:** Acute Treatment, Prevention'
    - Legacy single-tag: '**Acute Treatment**'

    Validates each tag against allowed options (case-insensitive).
    Returns the validated tag list, or None if no valid tags found.
    """
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # New format: **Tags:** Tag1, Tag2
        cleaned_upper = stripped.replace("**", "").strip().upper()
        if cleaned_upper.startswith("TAGS:"):
            # Strip all ** markers first, then extract after "Tags:"
            cleaned = stripped.replace("**", "").strip()
            after_prefix = cleaned.split(":", 1)[1].strip()
            raw_tags = [t.strip() for t in after_prefix.split(",") if t.strip()]
        else:
            # Legacy format: **Acute Treatment**
            cleaned = stripped.replace("**", "").strip()
            raw_tags = [cleaned] if cleaned else []

        # Validate each tag against allowed options
        validated: list[str] = []
        for raw in raw_tags:
            matched = _match_tag(raw, subdomain_options)
            if matched:
                validated.append(matched)
            else:
                logger.warning(
                    "Tag '%s' not in allowed options: %s",
                    raw,
                    subdomain_options,
                )

        return validated if validated else None
    return None


def _match_tag(raw: str, subdomain_options: list[str]) -> str | None:
    """Match a raw tag string against allowed options (case-insensitive)."""
    if raw in subdomain_options:
        return raw
    for option in subdomain_options:
        if raw.lower() == option.lower():
            return option
    return None


def _extract_citation(lines: list[str]) -> str | None:
    """Extract the citation line — the first non-empty line after the subdomain."""
    found_subdomain = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if not found_subdomain:
            # First non-empty line is the subdomain; skip it
            found_subdomain = True
            continue
        # This is the citation line
        return stripped
    return None


def _extract_after_marker(text: str, marker: str) -> str | None:
    """Extract text on the same line after a marker string."""
    if marker not in text:
        return None
    after = text.split(marker, 1)[1]
    # Take text until the next double newline or end
    result = after.split("\n\n", 1)[0].strip()
    return result if result else None


def _extract_key_finding(text: str) -> str | None:
    """Extract the key finding paragraph between Research Question and Details.

    The key finding is the paragraph after the Research Question paragraph
    and before the **Details:** section.
    """
    rq_marker = "**Research Question:**"
    details_marker = "**Details:**"

    if rq_marker not in text or details_marker not in text:
        return None

    # Get text between end of Research Question paragraph and Details
    after_rq = text.split(rq_marker, 1)[1]
    before_details = after_rq.split(details_marker, 1)[0]

    # The research question is the first paragraph; key finding is the second
    paragraphs = [p.strip() for p in before_details.split("\n\n") if p.strip()]
    if len(paragraphs) < 2:
        return None
    return paragraphs[1]


def _extract_detail_field(text: str, field_marker: str) -> str | None:
    """Extract a detail field value after its marker (e.g. '- Design: ...')."""
    if field_marker not in text:
        return None
    after = text.split(field_marker, 1)[1]
    # Take text until the next newline
    result = after.split("\n", 1)[0].strip()
    return result if result else None
