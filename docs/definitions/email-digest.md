# Email Digest

## Status
draft

## Version
v0

## Description
The assembled digest output — the pipeline's final product. Contains an opening, ordered article summaries with feedback links, and a closing. Produced in two formats: markdown (for rich email clients) and plain text (for simple pasting).

## Schema

```python
@dataclass
class EmailDigest:
    date_range: str              # Human-readable date range, e.g. "Mar 16 – Mar 22, 2026"
    article_count: int           # Number of summaries included
    title: str                   # Digest title from config
    opening: str                 # Rendered opening text (placeholders substituted)
    summaries: list[str]         # Rendered summary blocks, in display order
    closing: str                 # Closing text from config
    markdown: str                # Full markdown digest text
    plain_text: str              # Full plain-text digest text
```

## Constraints

- `article_count` must equal `len(summaries)`
- `markdown` and `plain_text` must contain identical content, differing only in formatting
- `summaries` order must reflect the `sort_by` setting from `distribute-config`
- Each summary block must include a feedback URL

## Changelog

| Date | Version | Change | Affected Specs |
|------|---------|--------|----------------|
| 2026-03-23 | v0 | Initial draft | — |
