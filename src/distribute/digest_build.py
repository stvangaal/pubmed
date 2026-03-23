# owner: digest-build
"""Assemble literature summaries into a formatted email digest.

Produces both markdown and plain-text versions of the digest,
writes them to output files, and prints the plain-text version to stdout.
Uses tiered rendering: full summary for high-scoring articles, short
teaser with blog link for the rest.
"""

from pathlib import Path

from src.models import (
    BlogPage,
    LiteratureSummary,
    EmailDigest,
    DistributeConfig,
    Subscriber,
    SubscriberDigest,
)


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
        return sorted(
            summaries, key=lambda s: (s.subdomain, -s.triage_score)
        )
    elif sort_by == "pub_date":
        return sorted(summaries, key=lambda s: s.pub_date, reverse=True)
    else:
        return sorted(summaries, key=lambda s: s.triage_score, reverse=True)


def _render_full_markdown(summary: LiteratureSummary) -> str:
    """Render a full summary in markdown format."""
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


def _render_full_plain(summary: LiteratureSummary) -> str:
    """Render a full summary in plain-text format."""
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


def _render_short_markdown(
    summary: LiteratureSummary, blog_url: str | None
) -> str:
    """Render a short teaser summary in markdown format."""
    read_more_url = blog_url or f"https://pubmed.ncbi.nlm.nih.gov/{summary.pmid}/"
    return (
        f"**{summary.subdomain}**\n"
        f"{summary.citation}\n"
        f"\n"
        f"{summary.summary_short}\n"
        f"\n"
        f"[Read full summary]({read_more_url}) · [Feedback]({summary.feedback_url})\n"
        f"\n"
        f"---"
    )


def _render_short_plain(
    summary: LiteratureSummary, blog_url: str | None
) -> str:
    """Render a short teaser summary in plain-text format."""
    pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{summary.pmid}/"
    read_more_url = blog_url or pubmed_url
    return (
        f"[{summary.subdomain}]\n"
        f"{summary.title}. {summary.journal}. PMID {summary.pmid} ({pubmed_url})\n"
        f"\n"
        f"{summary.summary_short}\n"
        f"\n"
        f"Full summary: {read_more_url}\n"
        f"Feedback: {summary.feedback_url}\n"
        f"\n"
        f"---"
    )


def _assemble_digest(
    summaries: list[LiteratureSummary],
    config: DistributeConfig,
    date_range: str,
    blog_page: BlogPage | None = None,
) -> EmailDigest:
    """Core assembly logic — builds an EmailDigest from summaries.

    Pure function with no side effects (no file I/O, no stdout).
    """
    article_count = len(summaries)

    # --- Opening ---
    opening_text = config.opening.format(
        date_range=date_range, article_count=article_count
    )

    # --- Closing ---
    closing_text = config.closing

    # --- Content ---
    empty_message = "No practice-relevant articles identified this week."

    if not summaries:
        markdown_body = empty_message
        plain_body = empty_message
        summary_texts: list[str] = []
    else:
        sorted_summaries = _sort_summaries(summaries, config.sort_by)

        # --- Table of contents ---
        md_toc = "\n".join(f"- {s.title}" for s in sorted_summaries)
        pt_toc = "\n".join(f"- {s.title}" for s in sorted_summaries)

        # --- Article summaries ---
        md_parts = []
        pt_parts = []

        for s in sorted_summaries:
            if s.triage_score >= config.full_summary_threshold:
                md_parts.append(_render_full_markdown(s))
                pt_parts.append(_render_full_plain(s))
            else:
                blog_url = (
                    blog_page.article_urls.get(s.pmid)
                    if blog_page
                    else None
                )
                md_parts.append(_render_short_markdown(s, blog_url))
                pt_parts.append(_render_short_plain(s, blog_url))

        markdown_body = md_toc + "\n\n---\n\n" + "\n\n".join(md_parts)
        plain_body = pt_toc + "\n\n---\n\n" + "\n\n".join(pt_parts)
        summary_texts = md_parts

    # --- Assemble full documents ---
    markdown_full = f"{opening_text}\n\n{markdown_body}\n\n{closing_text}\n"
    plain_full = f"{opening_text}\n\n{plain_body}\n\n{closing_text}\n"

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


def build_digest(
    summaries: list[LiteratureSummary],
    config: DistributeConfig,
    date_range: str,
    blog_page: BlogPage | None = None,
) -> EmailDigest:
    """Assemble summaries into a formatted digest.

    Uses tiered rendering: articles scoring >= full_summary_threshold get
    the full summary, articles below get a 2-sentence teaser with a blog link.
    Writes output files and prints the plain-text version to stdout.
    """
    digest = _assemble_digest(summaries, config, date_range, blog_page)

    # --- Write output files ---
    md_path = Path(config.output.file)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(digest.markdown)

    if config.output.plain_text:
        pt_path = Path(config.output.plain_text_file)
        pt_path.parent.mkdir(parents=True, exist_ok=True)
        pt_path.write_text(digest.plain_text)

    # --- Print plain text to stdout ---
    print(digest.plain_text)

    return digest


def build_subscriber_digests(
    summaries: list[LiteratureSummary],
    subscribers: list[Subscriber],
    config: DistributeConfig,
    date_range: str,
    blog_page: BlogPage | None = None,
) -> list[SubscriberDigest]:
    """Build one personalized digest per subscriber.

    Subscribers with empty subdomains receive all summaries.
    Subscribers with specific subdomains receive only matching articles.
    """
    results = []
    for sub in subscribers:
        if sub.subdomains:
            filtered = [s for s in summaries if s.subdomain in sub.subdomains]
        else:
            filtered = summaries

        digest = _assemble_digest(filtered, config, date_range, blog_page)
        results.append(SubscriberDigest(subscriber=sub, digest=digest))
    return results
