# PubMed Stroke Monitor

A weekly automated pipeline that identifies practice-changing clinical publications from PubMed, summarizes them using an LLM, and delivers curated digests for clinical audiences. Supports multiple clinical domains (stroke, neurology) via isolated config packages.

## What it does

```
PubMed API → Search → Filter → Summarize → Blog → Digest → Email
  ~50/week    rule-based   LLM triage    LLM summary   gh-pages   tiered     Resend
              + LLM        (~5-10/week)  (full+short)  archive    rendering  delivery
```

Every week, per domain, the pipeline:

1. **Searches** PubMed for domain literature indexed in the past 7 days (supports multiple topic queries with deduplication)
2. **Filters** aggressively — rule-based exclusions (animal studies, non-English, case reports), then LLM triage scoring for clinical relevance
3. **Summarizes** each selected article with a domain-specific LLM prompt that produces a structured clinical summary
4. **Publishes** each digest as a permanent blog page on GitHub Pages
5. **Assembles** an email digest with links to the blog page (full summaries for top articles, teasers for the rest)
6. **Emails** the digest to configured recipients via Resend
7. **Reports** a troubleshooting email to the domain owner with near-miss articles, LLM costs, and rejection details

## Sample output

Each article in the digest looks like this:

> **Acute Treatment**
> Safety and efficacy of direct versus conventional transfer to angiography suite... *The Lancet Neurology*. [41864232](https://pubmed.ncbi.nlm.nih.gov/41864232/)
>
> **Research Question:** Does bypassing standard CT imaging in favour of direct transfer to the angiography suite improve outcomes in patients with clinically suspected large vessel occlusion stroke?
>
> Direct transfer to angiography suite was stopped early for safety after symptomatic intracranial haemorrhage occurred in 15% of DTAS patients versus 0% of conventionally managed patients...
>
> **Details:**
> - Design: Multicentre open-label RCT, N=115
> - Primary outcome: mRS 0-2 at 90 days — 36% vs 42% (adjusted OR 0.73)
> - Limitations: Trial stopped early, underpowered for definitive conclusions

## Quick start

### Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/) (for LLM filtering and summarization)

### Setup

```bash
git clone <repo-url> && cd pubmed
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your-key-here
```

### Configure

Each domain has its own config package under `config/domains/{name}/`:

| File | What it controls |
|------|-----------------|
| `domain.yaml` | Schema version for the config package |
| `search-config.yaml` | PubMed query (MeSH terms, topics, date window) |
| `filter-config.yaml` | Rule-based filters + LLM triage (model, threshold, max articles) |
| `summary-config.yaml` | Summary format (model, prompt, subdomain tags, feedback form) |
| `blog-config.yaml` | Blog publishing (site URL, publish toggle, template paths) |
| `distribute-config.yaml` | Email digest template (opening, closing, sort order, output paths) |
| `email-config.yaml` | Email delivery (sender, recipients, subject template) |
| `prompts/triage-prompt.md` | System prompt for relevance scoring |
| `prompts/summary-prompt.md` | System prompt for article summarization |

Legacy flat config in `config/` is still supported when `--domain` is omitted.

### Run

```bash
# Run for a specific domain
python3 -m src.pipeline --domain stroke

# Run with legacy flat config (backward compatible)
python3 -m src.pipeline
```

### Add a new domain

1. Copy the template: `cp -r config/domains/_template config/domains/your-domain`
2. Fill in all `TODO` placeholders in the copied YAML files and prompts
3. Add your domain to the GitHub Actions matrix in `.github/workflows/weekly-digest.yml`

No source code changes required.

## Active domains

| Domain | MeSH Terms | Status |
|--------|-----------|--------|
| `stroke` | Stroke, cerebrovascular disorders | Active (weekly) |
| `neurology` | Neurology topics | Active (weekly) |

## Project structure

```
pubmed/
  config/
    domains/
      _template/             # Copy this to create a new domain
      stroke/                # Stroke domain config package
      neurology/             # Neurology domain config package
      CHANGELOG.md           # Config schema version history
    templates/               # Shared blog templates
      blog-post.md
      blog-index.md
    prompts/                 # Legacy flat prompts (backward compat)
    *.yaml                   # Legacy flat configs (backward compat)
  src/                       # Pipeline source code
    search/                  # Stage 1: PubMed API query + multi-topic search
    filter/                  # Stage 2: Rule filter + LLM triage
    summarize/               # Stage 3: LLM summarization
    distribute/              # Stage 4: Blog publish + email digest + troubleshooting report
    models.py                # Shared data models
    config.py                # Domain-aware config loader
    pipeline.py              # Orchestrator (--domain CLI)
  output/                    # Generated digests (gitignored)
  data/                      # Runtime state — seen PMIDs per domain (gitignored)
  docs/                      # Architecture, specs, definitions
    specs/                   # Implementation specifications
    definitions/             # Shared data contracts
  .github/workflows/         # GitHub Actions (matrix strategy per domain)
```

## How filtering works

The pipeline uses a two-pass hybrid filter to keep the digest high-signal:

**Pass 1 — Rule-based (free, fast):** Removes articles by language (non-English), study type (case reports, editorials, animal studies), and abstract availability. Typically removes 15-25% of results.

**Pass 2 — LLM triage (costs tokens, nuanced):** Scores surviving articles 0.00-1.00 for clinical relevance using a stroke-domain prompt. Articles scoring >= 0.70 are included (configurable). The prompt recognizes RCTs, guidelines, authoritative reviews from top journals, and imaging studies with diagnostic impact.

## Feedback

Each article in the digest includes a feedback link that pre-fills a Google Form with the article's PMID. Configure your Google Form URL and field ID in `config/summary-config.yaml`.

## Scheduling

The pipeline runs automatically every Monday at noon ET via GitHub Actions with a matrix strategy that runs each domain in parallel:

```yaml
# .github/workflows/weekly-digest.yml (simplified)
jobs:
  digest:
    strategy:
      matrix:
        domain: [stroke, neurology]
      fail-fast: false
    steps:
      - run: python3 -m src.pipeline --domain ${{ matrix.domain }}
```

To add a new domain to the schedule, add it to the `matrix.domain` list.

The pipeline publishes a blog page to GitHub Pages (via the `gh-pages` branch) and produces an email digest with links to the blog. GitHub Pages auto-deploys within ~60 seconds of the push.

## Blog archive

Each weekly digest is published as a permanent page at:

```
https://<username>.github.io/<repo>/digests/<date>/
```

Customize the blog page and index templates in `config/templates/`. Edit `config/blog-config.yaml` to set the site URL, title, and publishing behaviour. Set `publish: false` to skip blog publishing during local development.

## Cost

At typical volumes (~50 articles/week, ~5-10 summaries):
- LLM triage: ~$0.02/run (Sonnet 4.6)
- Summarization: ~$0.01/run (Sonnet 4.6)
- **Total: ~$0.03/week**

## License

MIT
