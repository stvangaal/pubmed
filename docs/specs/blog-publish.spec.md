---
name: blog-publish
status: draft
owner: distribute
owns:
  - src/distribute/blog_publish.py
  - tests/distribute/test_blog_publish.py
  - config/blog-config.yaml
  - config/templates/blog-post.md
  - config/templates/blog-index.md
requires:
  - name: literature-summary
    version: v0
  - name: blog-config
    version: v0
provides:
  - name: blog-page
    version: v0
---

# Blog Publish

## Status
draft

## Target Phase
Phase 3

## Purpose
Render weekly digests as Jekyll-compatible pages and publish them to a `gh-pages` branch, providing a permanent web archive of past digests. Runs before `digest-build` in the pipeline so that blog URLs are available for inclusion in the email digest.

## Requires (Inbound Contracts)

| Dependency | Source | Definition |
|------------|--------|------------|
| Literature summaries | summarize stage | `literature-summary` v0 |
| Blog configuration | user config | `blog-config` v0 |

## Provides (Outbound Contracts)

| Export | Type | Definition |
|--------|------|------------|
| Blog page (Jekyll markdown) | file committed to `gh-pages` | `blog-page` v0 |
| Blog page URL | string | deterministic URL returned to pipeline for use in email digest |

## Behaviour

### Input
A list of `LiteratureSummary` objects, a `BlogConfig`, a `date_range` string, and a `run_date` (ISO date string, e.g. `"2026-03-23"`).

### Page Rendering

#### Blog Post

Render the digest as a Jekyll markdown file using the **user-editable template** at `config/templates/blog-post.md`. The template uses the same `{placeholder}` convention as the email digest.

Available placeholders:
- `{title}` — from `blog-config.yaml` `site_title`
- `{date_range}` — human-readable date window
- `{run_date}` — ISO date for the run
- `{article_count}` — number of summaries
- `{articles}` — rendered article blocks (see below)
- `{closing}` — closing text from config

Each article is rendered with a per-article anchor (`<a id="pmid-{pmid}"></a>`) so individual articles are linkable from the email digest. The article rendering format is defined inline in the template using a `{%- for article in articles %}` / `{%- endfor %}` block — **not** Jinja, but a simple repeated section delimited by `<!-- BEGIN ARTICLE -->` and `<!-- END ARTICLE -->` markers. Within the article block, per-article placeholders are available:
- `{pmid}`, `{subdomain}`, `{citation}`, `{research_question}`, `{key_finding}`, `{design}`, `{primary_outcome}`, `{limitations}`, `{feedback_url}`, `{title}`, `{journal}`, `{pub_date}`

#### Index Page

Update `index.md` on the `gh-pages` branch to list all published digests, most recent first. The index uses the template at `config/templates/blog-index.md`.

Available placeholders:
- `{site_title}` — from config
- `{site_description}` — from config
- `{digest_list}` — rendered list of links, one per published digest

Each entry in the digest list is formatted as:
```
- [{date_range}]({baseurl}/digests/{run_date}) — {article_count} articles
```

The index is rebuilt on each run by scanning the `digests/` directory on `gh-pages` for existing posts (reading their front matter for date_range and article_count).

### URL Construction

Blog page URLs are deterministic:
```
{base_url}/digests/{run_date}
```

Per-article anchor URLs:
```
{base_url}/digests/{run_date}#pmid-{pmid}
```

The `base_url` is read from `blog-config.yaml`. This function returns a `BlogPage` object containing the page URL and per-article anchor URLs, which the pipeline passes to `digest-build`.

### Git Operations

Publishing to `gh-pages`:

1. Render the blog post markdown and index page to a temporary directory
2. Shell out to git:
   - `git worktree add <tmp> gh-pages` (create a temporary worktree for the `gh-pages` branch)
   - Copy rendered files into the worktree (`digests/{run_date}.md`, `index.md`)
   - `git add` + `git commit` with message `"Add digest {run_date}"`
   - `git push origin gh-pages`
   - `git worktree remove <tmp>`
3. Return the blog URL

If the `gh-pages` branch does not exist or `publish` is set to `false` in config, skip the git operations and return URLs based on the deterministic pattern (useful for local development and dry runs).

### Empty Digest

If the summary list is empty:
- Still publish a page with the "No practice-relevant articles identified this week." message
- Still update the index (shows "0 articles" for that week)
- This preserves the weekly publishing cadence for readers checking the archive

### Error Handling

- If git push fails (e.g. network error), log a warning and continue the pipeline — the email digest can still be produced without blog links, falling back to direct PubMed URLs
- If the `gh-pages` branch is missing and `publish` is true, log an error with setup instructions and skip publishing

## Decisions

| ID | Decision | Alternatives Considered | Rationale | Date |
|----|----------|------------------------|-----------|------|
| BP1 | User-editable templates for blog post and index | Hardcoded rendering in Python; Jinja2 templates | Templates as config files keep the code-vs-config separation consistent with the rest of the pipeline. Simple placeholder substitution (no Jinja dependency) keeps the dependency footprint minimal. | 2026-03-23 |
| BP2 | Git worktree for gh-pages operations | Checkout in-place; separate clone; GitHub API | Worktree avoids disrupting the main working tree. Separate clone is wasteful. GitHub API (contents endpoint) has file-size limits and is harder to debug. | 2026-03-23 |
| BP3 | Rebuild index from existing files on each run | Append-only index; separate index data file | Rebuild is idempotent — recovers from manual edits or partial failures. No separate state file to keep in sync. | 2026-03-23 |
| BP4 | Publish empty-week pages | Skip empty weeks | Preserves weekly cadence. Readers know the pipeline ran even if nothing was practice-changing. Avoids confusion about gaps. | 2026-03-23 |
| BP5 | Deterministic URLs independent of publish success | Wait for deployment confirmation | URLs are derived from config + date, not from GitHub's response. This lets the email be built immediately without waiting for Pages deployment. | 2026-03-23 |

## Additional Features to Consider

These are **not in scope** for the initial implementation but are natural extensions:

| Feature | Effort | Notes |
|---------|--------|-------|
| **RSS/Atom feed** | Low | Jekyll can auto-generate with the `jekyll-feed` plugin (add `plugins: [jekyll-feed]` to `_config.yml`). Zero code, just config. |
| **Custom domain** | Low | Add a `CNAME` file to `gh-pages` and configure DNS. No code change. |
| **Per-article standalone pages** | Medium | Each article gets its own page (good for social sharing). Requires a second template and changes URL structure. |
| **Theme customization** | Low | Swap `theme: minima` in `_config.yml` for another Jekyll theme. No pipeline change. |
| **Search** | Medium | Add a client-side search (e.g. lunr.js) to the archive. Requires a JSON index generated at build time. |

## Tests

### Unit Tests

- **test_render_blog_post**: Given summaries and config, verify the rendered markdown includes Jekyll front matter, all article anchors, and matches the template structure.
- **test_render_index**: Given a list of existing digest metadata, verify the index renders with all entries in reverse chronological order.
- **test_url_construction**: Given a base_url and run_date, verify page and per-article anchor URLs are correct.
- **test_article_placeholders**: Verify all per-article placeholders are substituted correctly.
- **test_empty_digest_page**: Given empty summaries, verify the page renders with the "no articles" message.
- **test_template_loading**: Verify templates are loaded from config/templates/ and placeholder substitution works.
- **test_publish_false_skips_git**: When `publish: false`, verify no git operations are attempted and URLs are still returned.

### Contract Tests

- **test_input_accepts_literature_summary**: Verify the builder accepts objects conforming to `literature-summary` v0.
- **test_config_matches_blog_config_schema**: Verify `config/blog-config.yaml` deserializes into a valid `BlogConfig`.
- **test_output_conforms_to_blog_page**: Verify the returned `BlogPage` object has the required fields.

### Integration Tests

- **test_worktree_publish**: In a test repo with a `gh-pages` branch, verify that `publish_to_gh_pages()` creates the correct commit with the expected files. (Uses a temporary git repo, not the real remote.)

## Implementation Notes

- The template engine is intentionally simple: `str.format_map()` for top-level placeholders, and a loop over the `<!-- BEGIN ARTICLE -->` / `<!-- END ARTICLE -->` block for per-article rendering. No Jinja2 dependency.
- The git worktree approach requires `fetch-depth: 0` in the GitHub Actions checkout step (already required for pushing to `gh-pages`).
- The `_config.yml` on `gh-pages` is managed manually (or by `init-blog` setup), not by the pipeline. The pipeline only adds/updates content files.
