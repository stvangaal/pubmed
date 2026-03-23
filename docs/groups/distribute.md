---
name: distribute
owner: architecture
---

# Distribute

## Purpose

Publish weekly digests as a permanent web archive (GitHub Pages) and assemble an email digest with links to the blog. The blog-publish spec runs first so that blog URLs are available for inclusion in the email digest.

## Boundaries

**Input:** `literature-summary@summarized` (~5 summaries)

**Output:** `blog-page@published` — Jekyll page committed to `gh-pages`; `email-digest@assembled` — markdown and plain-text digest with blog links

## Member Specs

| Spec | Responsibility |
|------|---------------|
| blog-publish | Render digest as a Jekyll page, push to `gh-pages` branch, return blog URLs |
| digest-build | Assemble summaries into email-ready text using configured template, with links pointing to blog pages |
| ~~email-send~~ | Deferred to future phase. The comms person copies the digest text into their email tooling. |

## Internal Structure

Two specs with a data dependency: blog-publish runs first and returns a `BlogPage` with the page URL and per-article anchor URLs. digest-build consumes these URLs to include blog links in the email digest. If blog-publish is disabled (`publish: false`) or fails, digest-build falls back to direct PubMed URLs.

## Boundary Definitions

| Definition | Access |
|------------|--------|
| `blog-config` | reads — site title, base URL, publish toggle, template paths |
| `distribute-config` | reads — digest title, opening/closing text, sort order, output paths |
| `literature-summary` | reads `@summarized` |
| `blog-page` | writes — Jekyll page committed to `gh-pages` |
| `email-digest` | writes — markdown and plain-text digest files |

## Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Paste-ready text, no automated sending | Removes email deliverability complexity (SPF, DKIM, bounce handling). Comms person handles distribution. Upgrade path: add email-send spec in future phase. |
| D2 | Both markdown and plain-text output | Some email clients strip markdown. Plain text ensures content is usable everywhere. |
| D3 | Blog-publish runs before digest-build | Blog URLs must exist before the email digest can link to them. Deterministic URLs mean the email doesn't need to wait for actual GitHub Pages deployment. |
| D4 | GitHub Pages via gh-pages branch | Free, markdown-native, zero additional infrastructure. Jekyll is built into GitHub Pages — no local install needed. |
