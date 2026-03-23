# PubMed Stroke Monitor

A weekly automated pipeline that identifies practice-changing stroke publications from PubMed, summarizes them using an LLM, and delivers a curated digest for clinical audiences.

## What it does

```
PubMed API → Search → Filter → Summarize → Blog + Digest
  ~50/week    rule-based   LLM triage    LLM summary    gh-pages archive
              + LLM        (~5-10/week)  (hybrid format) + email text
```

Every week, the pipeline:

1. **Searches** PubMed for stroke literature indexed in the past 7 days
2. **Filters** aggressively — rule-based exclusions (animal studies, non-English, case reports), then LLM triage scoring for clinical relevance
3. **Summarizes** each selected article with a stroke-domain LLM prompt that produces a structured clinical summary
4. **Publishes** each digest as a permanent blog page on GitHub Pages
5. **Assembles** an email digest with links to the blog page, ready to paste into an email

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

Edit the YAML files in `config/` to customize the pipeline for your domain:

| File | What it controls |
|------|-----------------|
| `config/search-config.yaml` | PubMed query (MeSH terms, date window) |
| `config/filter-config.yaml` | Rule-based filters + LLM triage (model, threshold, max articles) |
| `config/summary-config.yaml` | Summary format (model, prompt, subdomain tags, feedback form) |
| `config/blog-config.yaml` | Blog publishing (site URL, publish toggle, template paths) |
| `config/distribute-config.yaml` | Email digest template (opening, closing, sort order, output paths) |

LLM prompts are in `config/prompts/` and can be edited independently:

| File | Purpose |
|------|---------|
| `config/prompts/triage-prompt.md` | System prompt for relevance scoring (what makes an article practice-changing?) |
| `config/prompts/summary-prompt.md` | System prompt for article summarization (output format and tone) |

### Run

```bash
python3 -m src.pipeline
```

Output is written to `output/digest.md` (markdown) and `output/digest.txt` (plain text), and printed to stdout.

### Customize for your domain

The default configuration targets **stroke medicine**. To adapt for a different clinical domain:

1. Edit `config/search-config.yaml` — change `mesh_terms` to your domain's MeSH terms
2. Edit `config/filter-config.yaml` — update `priority_journals` and adjust `include_article_types`/`exclude_article_types` as needed
3. Edit `config/prompts/triage-prompt.md` — replace stroke-specific scoring guidance with your domain's criteria for "practice-changing"
4. Edit `config/prompts/summary-prompt.md` — update the subdomain tags and any domain-specific instructions

5. Edit `config/blog-config.yaml` — update `base_url` and `site_title` for your site

No source code changes required.

## Project structure

```
pubmed/
  config/                    # User-editable YAML config + LLM prompts
    prompts/
      triage-prompt.md       # LLM triage scoring prompt
      summary-prompt.md      # LLM summary generation prompt
    templates/
      blog-post.md           # Blog page template (editable)
      blog-index.md          # Blog index page template (editable)
    search-config.yaml
    filter-config.yaml
    summary-config.yaml
    blog-config.yaml         # Blog publishing settings
    distribute-config.yaml
  src/                       # Pipeline source code
    search/                  # Stage 1: PubMed API query
    filter/                  # Stage 2: Rule filter + LLM triage
    summarize/               # Stage 3: LLM summarization
    distribute/              # Stage 4: Blog publish + email digest
    models.py                # Shared data models
    config.py                # Config loader
    pipeline.py              # Orchestrator
  output/                    # Generated digests (gitignored)
  data/                      # Runtime state — seen PMIDs (gitignored)
  spikes/                    # Exploratory spike code (development only)
  docs/                      # Architecture, specs, definitions
```

## How filtering works

The pipeline uses a two-pass hybrid filter to keep the digest high-signal:

**Pass 1 — Rule-based (free, fast):** Removes articles by language (non-English), study type (case reports, editorials, animal studies), and abstract availability. Typically removes 15-25% of results.

**Pass 2 — LLM triage (costs tokens, nuanced):** Scores surviving articles 0.00-1.00 for clinical relevance using a stroke-domain prompt. Articles scoring >= 0.70 are included (configurable). The prompt recognizes RCTs, guidelines, authoritative reviews from top journals, and imaging studies with diagnostic impact.

## Feedback

Each article in the digest includes a feedback link that pre-fills a Google Form with the article's PMID. Configure your Google Form URL and field ID in `config/summary-config.yaml`.

## Scheduling

For automated weekly runs, use GitHub Actions:

```yaml
# .github/workflows/weekly-digest.yml
name: Weekly Stroke Digest
on:
  schedule:
    - cron: '0 8 * * 1'  # Every Monday at 8am UTC
  workflow_dispatch:       # Manual trigger for testing

permissions:
  contents: write          # Needed to push blog pages to gh-pages

jobs:
  digest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
        with:
          fetch-depth: 0   # Full history needed for gh-pages push
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - name: Configure git for blog publish
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
      - run: python3 -m src.pipeline
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      - uses: actions/upload-artifact@v4
        with:
          name: digest
          path: output/
```

The pipeline publishes a blog page to GitHub Pages (via the `gh-pages` branch) and produces a paste-ready email digest with links to the blog. GitHub Pages auto-deploys within ~60 seconds of the push.

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
