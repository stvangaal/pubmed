---
name: distribute
owner: architecture
---

# Distribute

## Purpose

Assemble individual literature summaries into a formatted digest ready to paste into an email. In v1, the output is text files (markdown + plain text) — automated sending is deferred.

## Boundaries

**Input:** `literature-summary@summarized` (~5 summaries)

**Output:** `email-digest` — markdown and plain-text files ready to paste into an email client

## Member Specs

| Spec | Responsibility |
|------|---------------|
| digest-build | Assemble summaries into digest text using configured template (opening, ordered summaries with feedback links, closing) |
| ~~email-send~~ | Deferred to v2. In v1, the comms person copies the digest text into their email tooling. |

## Internal Structure

Single spec in v1. The digest-build spec produces paste-ready text. When automated sending is added later, email-send would consume the digest-build output.

## Boundary Definitions

| Definition | Access |
|------------|--------|
| `distribute-config` | reads — digest title, opening/closing text, sort order, feedback form settings, output paths |
| `literature-summary` | reads `@summarized` |
| `email-digest` | writes — markdown and plain-text digest files |

## Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Paste-ready text in v1, no automated sending | Removes email deliverability complexity (SPF, DKIM, bounce handling). Comms person handles distribution. Upgrade path: add email-send spec in v2. |
| D2 | Both markdown and plain-text output | Some email clients strip markdown. Plain text ensures content is usable everywhere. |
