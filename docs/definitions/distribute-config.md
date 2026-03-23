# Distribute Config

## Status
draft

## Version
v0

## Description
User-facing configuration for the distribute stage. Controls the email digest template — opening text, closing text, ordering, and output paths. Users edit this as a YAML file without touching source code. Feedback form configuration lives in `summary-config` (where the per-article URLs are constructed).

## Schema

```yaml
# config/distribute-config.yaml

# Digest metadata
digest_title: "Stroke Literature Weekly"

# Opening text — appears before the article summaries
# Supports {date_range} and {article_count} placeholders
opening: |
  Here are this week's notable stroke publications ({date_range}).
  {article_count} articles selected from PubMed.

# Closing text — appears after the article summaries
closing: |
  This digest is auto-generated. For questions or to adjust the search criteria,
  contact the maintainer.

  Feedback on individual articles is welcome — use the feedback links above.

# How to order articles in the digest
sort_by: triage_score  # triage_score (default) | subdomain | pub_date

# Output settings
output:
  # Where to write the digest text
  file: "output/digest.md"
  # Also write a plain-text version (for pasting into email clients that strip markdown)
  plain_text: true
  plain_text_file: "output/digest.txt"
```

```python
@dataclass
class OutputConfig:
    file: str                    # Path for markdown digest output
    plain_text: bool             # Whether to also generate plain-text version
    plain_text_file: str         # Path for plain-text digest output

@dataclass
class DistributeConfig:
    digest_title: str            # Title for the digest
    opening: str                 # Opening text template with {date_range}, {article_count} placeholders
    closing: str                 # Closing text
    sort_by: str                 # Article sort order: "triage_score" | "subdomain" | "pub_date"
    output: OutputConfig
```

## Constraints

- `opening` may contain `{date_range}` and `{article_count}` placeholders — both are optional
- `closing` is plain text, no placeholders
- `sort_by` must be one of: `"triage_score"`, `"subdomain"`, `"pub_date"`
- `output.file` parent directory must exist or be creatable

## Changelog

| Date | Version | Change | Affected Specs |
|------|---------|--------|----------------|
| 2026-03-23 | v0 | Initial draft | — |
