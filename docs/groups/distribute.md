---
name: distribute
owner: architecture
---

# Distribute

## Purpose

Publish weekly digests as a permanent web archive (GitHub Pages), assemble an email digest with links to the blog, and send it to configured recipients via Resend. The three specs run in sequence: blog-publish → digest-build → email-send.

## Boundaries

**Input:** `literature-summary@summarized` (~5 summaries)

**Output:** `blog-page@published` — Jekyll page committed to `gh-pages`; `email-digest@assembled` — markdown and plain-text digest with blog links; email delivered to recipients via Resend

## Member Specs

| Spec | Responsibility |
|------|---------------|
| blog-publish | Render digest as a Jekyll page, push to `gh-pages` branch, return blog URLs |
| digest-build | Assemble summaries into email-ready text using configured template, with links pointing to blog pages |
| email-send | Send the assembled digest to configured recipients via Resend API |
| subscriber-preferences | Load subscriber profiles and filter digests by per-user subdomain preferences |

## Internal Structure

Three specs in sequence: blog-publish runs first and returns a `BlogPage` with the page URL and per-article anchor URLs. digest-build consumes these URLs to include blog links in the email digest. email-send takes the assembled digest and delivers it via Resend. If blog-publish is disabled or fails, digest-build falls back to direct PubMed URLs. If email-send fails, the digest files are still available for manual distribution.

## Boundary Definitions

| Definition | Access |
|------------|--------|
| `blog-config` | reads — site title, base URL, publish toggle, template paths |
| `distribute-config` | reads — digest title, opening/closing text, sort order, output paths |
| `literature-summary` | reads `@summarized` |
| `blog-page` | writes — Jekyll page committed to `gh-pages` |
| `email-config` | reads — sender, recipients, subject template, enabled toggle |
| `email-digest` | writes — markdown and plain-text digest files; reads — for email sending |

## Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Automated email via Resend + paste-ready files as fallback | SMTP; SendGrid; manual-only | Resend is simplest API with free tier. Digest files are still written for manual forwarding if email fails. |
| D2 | Both markdown and plain-text output | Some email clients strip markdown. Plain text ensures content is usable everywhere. |
| D3 | Blog-publish runs before digest-build | Blog URLs must exist before the email digest can link to them. Deterministic URLs mean the email doesn't need to wait for actual GitHub Pages deployment. |
| D4 | GitHub Pages via gh-pages branch | Free, markdown-native, zero additional infrastructure. Jekyll is built into GitHub Pages — no local install needed. |
