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
  - tests/distribute/test_wp_connection.py
  - tests/distribute/conftest.py
  - config/domains/_template/wp-config.yaml
  - config/domains/stroke/wp-config.yaml
  - config/domains/neurology/wp-config.yaml
  - wordpress/pubmed-pipeline.php
  - docs/wordpress-setup.md
  - .github/workflows/weekly-member-digest.yml
  - wordpress/pubmed-pipeline.php
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
Publish pipeline article summaries as WordPress posts via the REST API, and send per-member topic-filtered email digests by querying WordPress for member preferences. Each domain has its own WordPress site with independent credentials and configuration.

## Requires (Inbound Contracts)

| Dependency | Source | Definition |
|------------|--------|------------|
| Summarized articles | llm-summarize stage | `literature-summary` v0 |
| WordPress configuration | user config | `wp-config` v0 |

## Provides (Outbound Contracts)

None — terminal stage. Articles are published as WordPress posts; member digests are sent via Resend.

## Behaviour

### Article Publishing (`wp_publish.py`)

1. **Check preconditions.** Skip (log and return empty dict) if any of:
   - `config.enabled` is false
   - `config.site_url` is empty
   - Domain-scoped credential env vars (`config.env_username`, `config.env_app_password`) are not set

2. **Build auth header.** HTTP Basic Auth from the domain's `env_username` and `env_app_password` environment variables.

3. **Resolve taxonomy terms.** Fetch existing terms from `GET /wp-json/wp/v2/{clinical_topics_taxonomy}`. Create any missing terms via POST. Return a name→ID mapping.

4. **Create posts.** For each `LiteratureSummary`:
   - Render HTML content (citation, research question, key finding, study design, primary outcome, limitations, feedback link)
   - POST to `/wp-json/wp/v2/posts` with title, HTML content, `publish` status, taxonomy term IDs, and custom meta fields (pmid, triage_score, journal, pub_date, source_topic, preindex)
   - Return dict mapping PMID → WordPress post ID

### Member Querying (`wp_members.py`)

1. **Fetch members.** GET `/wp-json/digest/v1/members` with `X-Digest-Secret` header (from `config.env_digest_secret` env var).
2. **Parse response.** Return list of `Member` objects (email, display_name, topics). Skip entries without email addresses.
3. **Error handling.** Return empty list on any failure — log warning but don't halt.

### Per-Member Digest (`wp_digest.py`)

1. **Fetch recent posts** from WordPress REST API (last N days, configurable via `--days`).
2. **Fetch members** via the custom endpoint using the domain-scoped digest secret.
3. **Filter posts per member** based on topic preferences.
4. **Send filtered digests** via Resend API — each member receives only articles matching their selected topics.

### WordPress Plugin (`wordpress/pubmed-pipeline.php`)

A micro-plugin installed on each WordPress site that registers:
- `clinical_topics` custom taxonomy (public, REST-enabled)
- 6 article meta fields exposed via REST API: `pmid`, `triage_score`, `journal`, `pub_date`, `source_topic`, `preindex`
- Custom REST endpoint `GET /wp-json/digest/v1/members` protected by `WP_DIGEST_API_SECRET` constant

### Domain-Scoped Credentials

Each domain declares its own environment variable names in `wp-config.yaml`:

```yaml
env_username: "WP_STROKE_USERNAME"
env_app_password: "WP_STROKE_APP_PASSWORD"
env_digest_secret: "WP_STROKE_DIGEST_SECRET"
```

Production code reads credentials from these config-driven names, not hardcoded values. GitHub Actions workflows pass domain-specific secrets as the corresponding env vars.

## Decisions

| ID | Decision | Alternatives Considered | Rationale | Date |
|----|----------|------------------------|-----------|------|
| WP1 | WordPress REST API for article publishing | Kit (ConvertKit); custom CMS; static site only | WordPress provides a member portal, topic-based taxonomy, and REST API out of the box. Sites are already WordPress. | 2026-03-30 |
| WP2 | Application Passwords for auth | OAuth; JWT; custom token | Built into WordPress core since 5.6, no plugins needed, simple Basic Auth over HTTPS. | 2026-03-30 |
| WP3 | Custom REST endpoint for member preferences | Direct DB query; wp-admin export; Ultimate Member API | Decouples the digest script from WordPress internals. The endpoint returns exactly the data needed (email + topics) with secret-based auth. | 2026-03-30 |
| WP4 | Micro-plugin for taxonomy + meta + endpoint | Theme functions.php; multiple plugins | Single file, easy to version control and deploy. All pipeline requirements in one plugin. | 2026-04-02 |
| WP5 | Domain-scoped credential env vars | Single shared WP_USERNAME/WP_APP_PASSWORD | Each domain is a separate WordPress site with its own users. Shared credentials would require all sites to use the same admin account. Config-driven names allow independent rotation. | 2026-04-04 |
| WP6 | Live connection tests with pytest markers | Manual curl verification; no automated testing | Automated verification that each site has the plugin installed, taxonomy registered, meta fields exposed, and auth working. Gated behind `live`/`live_write` markers so they don't run in CI without credentials. | 2026-04-04 |

## Tests

### Unit Tests (`test_wp_publish.py`, `test_wp_members.py`)

- **test_basic_auth_encoding**: Verify auth header encodes username:password as Base64.
- **test_contains_all_sections**: Verify rendered HTML includes all article sections.
- **test_includes_feedback_link**: Verify feedback URL appears in HTML when provided.
- **test_no_feedback_link_when_empty**: Verify feedback link is omitted when URL is empty.
- **test_skips_when_disabled**: When `enabled: false`, verify no API calls and empty result.
- **test_skips_when_no_site_url**: When `site_url` is empty, verify no API calls.
- **test_skips_when_no_credentials**: When env vars are missing, verify no API calls.
- **test_creates_posts**: Verify full publish flow with mocked httpx (taxonomy resolution + post creation).
- **test_fetches_members**: Verify member parsing from JSON response.
- **test_skips_entries_without_email**: Verify entries with empty email are filtered out.
- **test_returns_empty_on_failure**: Verify graceful failure returns empty list.
- **test_sends_api_secret_header**: Verify X-Digest-Secret header is sent when secret is provided.

### Live Connection Tests (`test_wp_connection.py`)

Gated behind `@pytest.mark.live` (read-only) and `@pytest.mark.live_write` (creates+deletes posts). Parametrized across all domains auto-discovered from `config/domains/*/wp-config.yaml`. Require domain-scoped credential env vars; skip gracefully when missing.

- **TestWpApiReachable**: REST API root responds 200, `wp/v2` namespace present.
- **TestClinicalTopicsTaxonomy**: Taxonomy endpoint exists, `rest_base` matches config.
- **TestArticleMetaFields**: Post schema includes all `expected_meta_fields` from config.
- **TestAuthentication**: Authenticated `/users/me` succeeds; unauthenticated POST returns 401.
- **TestDigestMembersEndpoint**: Members endpoint returns 200 with valid secret, rejects bad secret, `digest/v1` namespace discoverable.
- **TestPostLifecycle** (`live_write`): Create draft post with meta → verify meta persisted → delete via API.

## Implementation Notes

- The WordPress plugin (`wordpress/pubmed-pipeline.php`) must be installed and activated on each domain's WordPress site. See `docs/wordpress-setup.md` for the full setup guide.
- Live tests auto-discover domains by scanning `config/domains/*/wp-config.yaml` (excluding `_template`). Adding a new domain automatically includes it in the test suite.
- `pyproject.toml` registers the `live` and `live_write` markers and deselects them by default, so `pytest` only runs unit tests.
