# Blog Page

## Status
draft

## Version
v0

## Description
The output of the blog-publish stage — a rendered Jekyll page committed to `gh-pages`, plus the deterministic URLs needed by the email digest to link to individual articles on the blog.

## Schema

```python
@dataclass
class BlogPage:
    run_date: str                       # ISO date, e.g. "2026-03-23"
    page_url: str                       # Full URL to the digest page
    article_urls: dict[str, str]        # PMID → full anchor URL (e.g. "https://...#pmid-39876543")
    markdown: str                       # Rendered page markdown (with Jekyll front matter)
    published: bool                     # Whether the page was actually pushed to gh-pages
```

## Constraints

- `page_url` must be a valid URL matching pattern `{base_url}/{digests_dir}/{run_date}`
- `article_urls` keys must be PMIDs present in the input summaries
- `article_urls` values must be `{page_url}#pmid-{pmid}`
- `published` is false when `blog-config.publish` is false or git push failed
- `markdown` includes Jekyll front matter (`---` delimited YAML block)

## Changelog

| Date | Version | Change | Affected Specs |
|------|---------|--------|----------------|
| 2026-03-23 | v0 | Initial draft | — |
