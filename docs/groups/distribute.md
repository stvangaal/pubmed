---
name: distribute
owner: architecture
---

# Distribute

## Purpose

Publish weekly digests as a permanent web archive (GitHub Pages), assemble an email digest with links to the blog, send it to configured recipients via Resend, and publish article summaries to domain-specific WordPress sites with per-member topic-filtered digests. The core specs run in sequence: blog-publish → digest-build → email-send. WordPress publishing (wp-publish) runs in parallel with blog-publish.

## Boundaries

**Input:** `literature-summary@summarized` (~5 summaries)

**Output:** `blog-page@published` — Jekyll page committed to `gh-pages`; `email-digest@assembled` — markdown and plain-text digest with blog links; email delivered to recipients via Resend; WordPress posts created on domain-specific sites; per-member topic-filtered digests sent via Resend

## Member Specs

| Spec | Responsibility |
|------|---------------|
| blog-publish | Render digest as a Jekyll page, push to `gh-pages` branch, return blog URLs |
| digest-build | Assemble summaries into email-ready text using configured template, with links pointing to blog pages |
| email-send | Send the assembled digest to configured recipients via Resend API |
| wp-publish | Publish articles as WordPress posts, query member preferences, send per-member topic-filtered digests |

## Internal Structure

Three core specs in sequence: blog-publish runs first and returns a `BlogPage` with the page URL and per-article anchor URLs. digest-build consumes these URLs to include blog links in the email digest. email-send takes the assembled digest and delivers it via Resend. If blog-publish is disabled or fails, digest-build falls back to direct PubMed URLs. If email-send fails, the digest files are still available for manual distribution.

wp-publish runs in parallel with the blog pipeline. It publishes article summaries as WordPress posts (with taxonomy terms and custom meta fields), then queries the WordPress site for member topic preferences and sends per-member filtered digests via Resend. Each domain has its own WordPress site with independent credentials configured in `wp-config.yaml`.

## Boundary Definitions

| Definition | Access |
|------------|--------|
| `blog-config` | reads — site title, base URL, publish toggle, template paths |
| `distribute-config` | reads — digest title, opening/closing text, sort order, output paths |
| `literature-summary` | reads `@summarized` |
| `blog-page` | writes — Jekyll page committed to `gh-pages` |
| `email-config` | reads — sender, recipients, subject template, enabled toggle |
| `email-digest` | writes — markdown and plain-text digest files; reads — for email sending |
| `wp-config` | reads — site URL, taxonomy slug, credential env var names, expected meta fields |

## Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Automated email via Resend + paste-ready files as fallback | SMTP; SendGrid; manual-only | Resend is simplest API with free tier. Digest files are still written for manual forwarding if email fails. |
| D2 | Both markdown and plain-text output | Some email clients strip markdown. Plain text ensures content is usable everywhere. |
| D3 | Blog-publish runs before digest-build | Blog URLs must exist before the email digest can link to them. Deterministic URLs mean the email doesn't need to wait for actual GitHub Pages deployment. |
| D4 | GitHub Pages via gh-pages branch | Free, markdown-native, zero additional infrastructure. Jekyll is built into GitHub Pages — no local install needed. |
