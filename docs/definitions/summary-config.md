# Summary Config

## Status
draft

## Version
v0

## Description
User-facing configuration for the summarization stage. Controls the LLM prompt template, output format, and model parameters. Users edit this as a YAML file without touching source code.

## Schema

```python
@dataclass
class SummaryConfig:
    prompt_template: str         # LLM prompt template with {title}, {journal}, {authors}, {pmid}, {article_types}, {abstract} placeholders
    model: str                   # LLM model identifier, e.g. "claude-sonnet-4-6"
    max_tokens: int              # Max tokens for LLM response
    subdomain_options: list[str] # Allowed subdomain tags, e.g. ["Acute Treatment", "Prevention", "Rehabilitation", "Hospital Care", "Imaging", "Epidemiology"]
    feedback_form_url: str       # Google Form base URL for per-article feedback links
    feedback_pmid_field: str     # Google Form field ID for PMID pre-fill parameter
```

## Constraints

- `prompt_template` must contain all six placeholders: `{title}`, `{journal}`, `{authors}`, `{pmid}`, `{article_types}`, `{abstract}`
- `subdomain_options` must have at least one entry
- `max_tokens` must be between 100 and 2000
- `feedback_form_url` must be a valid HTTPS URL
- `feedback_pmid_field` must be a non-empty string (Google Form entry ID, e.g. "entry.123456789")

## Changelog

| Date | Version | Change | Affected Specs |
|------|---------|--------|----------------|
| 2026-03-23 | v0 | Initial draft from architecture spike | — |
