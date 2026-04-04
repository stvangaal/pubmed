---
name: wp-publish
status: in-progress
owner: distribute
owns:
  - src/distribute/wp_publish.py
  - src/distribute/wp_members.py
  - src/distribute/wp_digest.py
  - tests/distribute/test_wp_publish.py
  - tests/distribute/test_wp_members.py
  - wordpress/pubmed-pipeline.php
  - docs/wordpress-setup.md
  - config/domains/_template/wp-config.yaml
  - config/domains/stroke/wp-config.yaml
  - config/domains/neurology/wp-config.yaml
  - .github/workflows/weekly-member-digest.yml
requires:
  - name: literature-summary
    version: v0
  - name: wp-config
    version: v0
provides: []
---

# WordPress Publish

## Status
in-progress

## Target Phase
Phase 3

## Purpose
Upload summarized articles as WordPress posts via the REST API, enabling a domain-specific website with taxonomy-based browsing and member signups. Also provides a member digest system that fetches subscriber preferences from WordPress and delivers personalized, topic-filtered email digests.

## Requires (Inbound Contracts)

| Dependency | Source | Definition |
|------------|--------|------------|
| Literature summaries | summarize stage | `literature-summary` v0 |
| WordPress configuration | user config | `wp-config` v0 |

## Provides (Outbound Contracts)

None — terminal stage. Posts are the final output on the WordPress site.

## Behaviour

### Article Publishing

Each `LiteratureSummary` becomes a WordPress post with:
- Title and rendered HTML content (research question, key finding, design, primary outcome, limitations, feedback link)
- Clinical topic taxonomy terms mapped from article tags (auto-created if missing)
- Custom meta fields: `pmid`, `triage_score`, `journal`, `pub_date`, `source_topic`, `preindex`

Authentication uses WordPress Application Passwords via `WP_USERNAME` and `WP_APP_PASSWORD` environment variables.

### Precondition Checks

Skip publishing (log and return) if any of:
- `config.enabled` is false
- `config.site_url` is empty
- `WP_USERNAME` or `WP_APP_PASSWORD` not set

### Taxonomy Resolution

Before creating posts, resolve all unique tags across summaries to WordPress taxonomy term IDs. Fetch existing terms via `GET /wp-json/wp/v2/{taxonomy}`, create missing terms via `POST`. Cache the mapping for the duration of the run.

### Member Digest

A separate workflow (`weekly-member-digest.yml`) fetches registered members and their topic preferences from a custom WordPress REST endpoint (`/wp-json/digest/v1/members`), then builds and sends per-member filtered digests via Resend. Protected by a shared secret (`WP_DIGEST_API_SECRET`).

### WordPress Plugin

`wordpress/pubmed-pipeline.php` is a micro-plugin that registers:
1. `clinical_topics` custom taxonomy on posts
2. Article meta fields (`pmid`, `triage_score`, `journal`, `pub_date`, `source_topic`, `preindex`) exposed via REST
3. Custom REST endpoint for member preferences (`/digest/v1/members`)

### Error Handling

- Failed post creation logs a warning and continues to next article — does not halt the pipeline
- Failed taxonomy term creation logs a warning — posts without terms still succeed

## Decisions

| ID | Decision | Alternatives Considered | Rationale | Date |
|----|----------|------------------------|-----------|------|
| WP1 | WordPress REST API for article publishing | Direct DB access; XML-RPC; git deploy theme with content | REST API is the modern WordPress integration path, works with any host, uses standard auth. | 2026-03-30 |
| WP2 | Application Passwords for auth | OAuth; JWT; custom token | Built into WordPress 5.6+, no plugins needed. Simple for CI/CD — just env vars. | 2026-03-30 |
| WP3 | Custom micro-plugin rather than theme functions.php | functions.php; full plugin with admin UI | Plugin is portable across themes, can be version-controlled in the repo, minimal code. | 2026-03-30 |
| WP4 | Shared secret for member endpoint | OAuth; no auth; WordPress cookie auth | Simple, stateless, works from CI. The endpoint only returns emails + display names — not high-sensitivity. | 2026-03-30 |

## Tests

### Unit Tests

- **test_render_article_html**: Verify HTML rendering includes all summary sections and feedback link.
- **test_skip_when_disabled**: When `enabled: false`, verify no API calls.
- **test_skip_when_no_credentials**: When env vars unset, verify no API calls.
- **test_build_auth_header**: Verify base64 encoding of credentials.

### Contract Tests

- **test_config_matches_wp_config_schema**: Verify `wp-config.yaml` deserializes into `WordPressConfig`.

### Integration Tests

- **test_publish_real_post**: Publish a test article to a real WordPress site. (Requires credentials; skip in CI if unavailable.)

## Environment Requirements

- WordPress 6.0+ with REST API enabled
- SSL certificate (required for Application Password auth)
- `pubmed-pipeline.php` plugin activated
- Environment variables: `WP_USERNAME`, `WP_APP_PASSWORD`, `WP_DIGEST_API_SECRET`

## Implementation Notes

- Uses `httpx` for HTTP requests (consistent with rest of pipeline).
- Posts are always created fresh — no deduplication by PMID. The pipeline runs weekly; duplicates are prevented by the upstream `seen_pmids.json` deduplication.
