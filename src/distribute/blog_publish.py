# owner: blog-publish
"""Render weekly digests as Jekyll pages and publish to gh-pages.

Produces a blog post markdown file with per-article anchors, updates
the index page, and pushes both to the gh-pages branch via git worktree.
"""

import logging
import re
import subprocess
import tempfile
from pathlib import Path

from src.models import BlogConfig, BlogPage, LiteratureSummary

logger = logging.getLogger(__name__)


def publish_blog(
    summaries: list[LiteratureSummary],
    config: BlogConfig,
    date_range: str,
    run_date: str,
) -> BlogPage:
    """Render and publish a blog digest page.

    Args:
        summaries: LiteratureSummary objects to render.
        config: BlogConfig with site metadata and template paths.
        date_range: Human-readable date window, e.g. "Mar 16 – Mar 22, 2026".
        run_date: ISO date string, e.g. "2026-03-23".

    Returns:
        BlogPage with the page URL, per-article anchor URLs, rendered
        markdown, and whether the page was actually published.
    """
    # Build deterministic URLs
    page_url = f"{config.base_url}/{config.digests_dir}/{run_date}"
    article_urls = {
        s.pmid: f"{page_url}#pmid-{s.pmid}" for s in summaries
    }

    # Render the blog post
    post_markdown = _render_post(summaries, config, date_range, run_date)

    # Publish to gh-pages if enabled
    published = False
    if config.publish:
        published = _publish_to_gh_pages(
            post_markdown, config, date_range, run_date, len(summaries)
        )
    else:
        logger.info("Blog publishing disabled (publish: false), skipping git push")

    return BlogPage(
        run_date=run_date,
        page_url=page_url,
        article_urls=article_urls,
        markdown=post_markdown,
        published=published,
    )


def _render_post(
    summaries: list[LiteratureSummary],
    config: BlogConfig,
    date_range: str,
    run_date: str,
) -> str:
    """Render the blog post markdown from the template."""
    template = Path(config.templates.post).read_text()

    # Split template into header, article block, and footer
    article_block, header, footer = _split_template(template)

    # Render articles
    if summaries:
        rendered_articles = []
        for s in summaries:
            rendered = article_block.format_map(_article_placeholders(s))
            rendered_articles.append(rendered)
        articles_text = "\n".join(rendered_articles)
    else:
        articles_text = "\nNo practice-relevant articles identified this week.\n"

    # Render the full page (header + articles + footer)
    full_template = header + articles_text + footer
    return full_template.format_map({
        "site_title": config.site_title,
        "date_range": date_range,
        "run_date": run_date,
        "article_count": str(len(summaries)),
        "closing": config.closing,
    })


def _split_template(template: str) -> tuple[str, str, str]:
    """Split template into (article_block, header, footer).

    The article block is the text between <!-- BEGIN ARTICLE --> and
    <!-- END ARTICLE --> markers. Header is everything before the begin
    marker, footer is everything after the end marker.
    """
    begin_marker = "<!-- BEGIN ARTICLE -->"
    end_marker = "<!-- END ARTICLE -->"

    begin_idx = template.index(begin_marker)
    end_idx = template.index(end_marker) + len(end_marker)

    header = template[:begin_idx]
    article_block = template[begin_idx + len(begin_marker):end_idx - len(end_marker)]
    footer = template[end_idx:]

    return article_block, header, footer


def _article_placeholders(summary: LiteratureSummary) -> dict[str, str]:
    """Build the placeholder dict for a single article."""
    return {
        "pmid": summary.pmid,
        "subdomain": summary.subdomain,
        "citation": summary.citation,
        "research_question": summary.research_question,
        "key_finding": summary.key_finding,
        "design": summary.design,
        "primary_outcome": summary.primary_outcome,
        "limitations": summary.limitations,
        "summary_short": summary.summary_short,
        "feedback_url": summary.feedback_url,
        "title": summary.title,
        "journal": summary.journal,
        "pub_date": summary.pub_date,
    }


def _publish_to_gh_pages(
    post_markdown: str,
    config: BlogConfig,
    date_range: str,
    run_date: str,
    article_count: int,
) -> bool:
    """Push the rendered post and updated index to gh-pages via git worktree.

    Returns True if the push succeeded, False otherwise.
    """
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "gh-pages"

            # Create worktree
            _run_git(["worktree", "add", str(tmp_path), config.branch])

            try:
                # Write the blog post
                digests_dir = tmp_path / config.digests_dir
                digests_dir.mkdir(parents=True, exist_ok=True)
                post_path = digests_dir / f"{run_date}.md"
                post_path.write_text(post_markdown)

                # Rebuild the index
                index_markdown = _rebuild_index(tmp_path, config)
                (tmp_path / "index.md").write_text(index_markdown)

                # Commit and push with retry — parallel matrix jobs may
                # race on the gh-pages branch, so pull --rebase before
                # retrying a failed push.
                max_retries = 3
                for attempt in range(max_retries):
                    _run_git(["add", "."], cwd=tmp_path)

                    # Check if there are changes to commit
                    result = _run_git(
                        ["diff", "--cached", "--quiet"],
                        cwd=tmp_path,
                        check=False,
                    )
                    if result.returncode == 0:
                        logger.info("No changes to commit to gh-pages")
                        return True

                    _run_git(
                        ["commit", "-m", f"Add digest {run_date}"],
                        cwd=tmp_path,
                    )

                    push_result = _run_git(
                        ["push", "origin", config.branch],
                        cwd=tmp_path,
                        check=False,
                    )
                    if push_result.returncode == 0:
                        logger.info("Published blog page for %s", run_date)
                        return True

                    # Push failed — likely a concurrent update to gh-pages.
                    # Pull with rebase, re-apply our changes, and retry.
                    logger.warning(
                        "Push to gh-pages failed (attempt %d/%d), "
                        "rebasing and retrying: %s",
                        attempt + 1,
                        max_retries,
                        push_result.stderr.strip(),
                    )
                    _run_git(
                        ["pull", "--rebase", "origin", config.branch],
                        cwd=tmp_path,
                    )

                # All retries exhausted
                logger.error(
                    "Failed to push to gh-pages after %d attempts",
                    max_retries,
                )
                return False

            finally:
                # Clean up worktree
                _run_git(["worktree", "remove", str(tmp_path), "--force"])

    except Exception:
        logger.warning(
            "Failed to publish blog page — continuing without blog links",
            exc_info=True,
        )
        return False


def _rebuild_index(worktree_path: Path, config: BlogConfig) -> str:
    """Rebuild index.md by scanning existing digest files on gh-pages."""
    template = Path(config.templates.index).read_text()
    digests_dir = worktree_path / config.digests_dir

    entries = []
    if digests_dir.exists():
        for md_file in sorted(digests_dir.glob("*.md"), reverse=True):
            meta = _read_front_matter(md_file)
            if meta:
                entry_date = md_file.stem  # e.g. "2026-03-23"
                title = meta.get("title", entry_date)
                count = meta.get("article_count", "?")
                url = f"{config.digests_dir}/{entry_date}"
                entries.append(f"- [{title}]({url}) — {count} articles")

    digest_list = "\n".join(entries) if entries else "No digests published yet."

    return template.format_map({
        "site_title": config.site_title,
        "site_description": config.site_description,
        "digest_list": digest_list,
    })


def _read_front_matter(path: Path) -> dict | None:
    """Read YAML front matter from a Jekyll markdown file."""
    try:
        text = path.read_text()
        if not text.startswith("---"):
            return None
        # Find the closing ---
        end = text.index("---", 3)
        front = text[3:end].strip()
        # Simple key: value parsing (avoids importing yaml in this module)
        result = {}
        for line in front.split("\n"):
            if ":" in line:
                key, _, value = line.partition(":")
                value = value.strip().strip('"').strip("'")
                result[key.strip()] = value
        return result
    except Exception:
        return None


def _run_git(
    args: list[str],
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Run a git command."""
    cmd = ["git"] + args
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )
