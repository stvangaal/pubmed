# owner: digest-build
"""Assemble literature summaries into a formatted email digest.

Produces both markdown and plain-text versions of the digest,
writes them to output files, and prints the plain-text version to stdout.
"""

from pathlib import Path

from src.models import LiteratureSummary, EmailDigest, DistributeConfig


def _sort_summaries(
    summaries: list[LiteratureSummary], sort_by: str
) -> list[LiteratureSummary]:
    """Sort summaries according to the configured strategy.

    - "triage_score": highest relevance first (descending).
    - "subdomain": grouped alphabetically by subdomain, then by score
      within each group (descending).
    - "pub_date": most recent publication date first (descending; ISO
      date strings sort lexicographically).
    """
    if sort_by == "subdomain":
        # Primary key: subdomain alphabetically. Secondary: score descending.
        return sorted(
            summaries, key=lambda s: (s.subdomain, -s.triage_score)
        )
    elif sort_by == "pub_date":
        return sorted(summaries, key=lambda s: s.pub_date, reverse=True)
    else:
        # Default: triage_score descending
        return sorted(summaries, key=lambda s: s.triage_score, reverse=True)


def _render_summary_markdown(summary: LiteratureSummary) -> str:
    """Render a single summary in the markdown hybrid format."""
    return (
        f"**{summary.subdomain}**\n"
        f"{summary.citation}\n"
        f"\n"
        f"**Research Question:** {summary.research_question}\n"
        f"\n"
        f"{summary.key_finding}\n"
        f"\n"
        f"**Details:**\n"
        f"- Design: {summary.design}\n"
        f"- Primary outcome: {summary.primary_outcome}\n"
        f"- Limitations: {summary.limitations}\n"
        f"\n"
        f"[Feedback on this article]({summary.feedback_url})\n"
        f"\n"
        f"---"
    )


def _render_summary_plain(summary: LiteratureSummary) -> str:
    """Render a single summary in plain-text format (no markdown syntax)."""
    pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{summary.pmid}/"
    return (
        f"[{summary.subdomain}]\n"
        f"{summary.title}. {summary.journal}. PMID {summary.pmid} ({pubmed_url})\n"
        f"\n"
        f"Research Question: {summary.research_question}\n"
        f"\n"
        f"{summary.key_finding}\n"
        f"\n"
        f"Details:\n"
        f"- Design: {summary.design}\n"
        f"- Primary outcome: {summary.primary_outcome}\n"
        f"- Limitations: {summary.limitations}\n"
        f"\n"
        f"Feedback: {summary.feedback_url}\n"
        f"\n"
        f"---"
    )


def build_digest(
    summaries: list[LiteratureSummary],
    config: DistributeConfig,
    date_range: str,
) -> EmailDigest:
    """Assemble summaries into a formatted digest.

    Sorts summaries per config.sort_by, renders opening/content/closing in
    both markdown and plain-text formats, writes output files, prints the
    plain-text version to stdout, and returns an EmailDigest object.
    """
    article_count = len(summaries)

    # --- Opening ---
    # Substitute {date_range} and {article_count} placeholders in the
    # opening template. Using str.format_map so missing keys don't raise.
    opening_text = config.opening.format(
        date_range=date_range, article_count=article_count
    )

    # --- Closing ---
    closing_text = config.closing

    # --- Content ---
    empty_message = "No practice-relevant articles identified this week."

    if not summaries:
        # Empty digest: opening + notice + closing
        markdown_body = empty_message
        plain_body = empty_message
        summary_texts: list[str] = []
    else:
        sorted_summaries = _sort_summaries(summaries, config.sort_by)
        md_parts = [_render_summary_markdown(s) for s in sorted_summaries]
        pt_parts = [_render_summary_plain(s) for s in sorted_summaries]

        markdown_body = "\n\n".join(md_parts)
        plain_body = "\n\n".join(pt_parts)
        summary_texts = md_parts

    # --- Assemble full documents ---
    markdown_full = f"{opening_text}\n\n{markdown_body}\n\n{closing_text}\n"
    plain_full = f"{opening_text}\n\n{plain_body}\n\n{closing_text}\n"

    # --- Write output files ---
    md_path = Path(config.output.file)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(markdown_full)

    if config.output.plain_text:
        pt_path = Path(config.output.plain_text_file)
        pt_path.parent.mkdir(parents=True, exist_ok=True)
        pt_path.write_text(plain_full)

    # --- Print plain text to stdout ---
    print(plain_full)

    # --- Return EmailDigest ---
    return EmailDigest(
        date_range=date_range,
        article_count=article_count,
        title=config.digest_title,
        opening=opening_text,
        summaries=summary_texts,
        closing=closing_text,
        markdown=markdown_full,
        plain_text=plain_full,
    )
