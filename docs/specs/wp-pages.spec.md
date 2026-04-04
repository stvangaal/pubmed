---
name: wp-pages
status: in-progress
owner: distribute
owns:
  - src/distribute/wp_pages.py
  - tests/distribute/test_wp_pages.py
  - content/pages/_defaults/privacy-policy.md
  - content/pages/_defaults/terms-of-use.md
  - content/pages/_defaults/disclaimer.md
  - content/pages/_defaults/about.md
  - content/pages/_defaults/landing.md
  - .github/workflows/sync-wp-pages-stroke.yml
  - .github/workflows/sync-wp-pages-neurology.yml
requires:
  - name: wp-config
    version: v0
provides: []
---

# WordPress Pages

## Status
draft

## Target Phase
Phase 3

## Purpose
Manage static website content (landing page, about, disclaimer, privacy policy, terms of use) as version-controlled Markdown files in the repository, with automatic sync to WordPress via the REST API. Domains inherit sensible defaults and can override any page.

## Requires (Inbound Contracts)

| Dependency | Source | Definition |
|------------|--------|------------|
| WordPress configuration | user config | `wp-config` v0 |

## Provides (Outbound Contracts)

None — pages are the final output on the WordPress site.

## Behaviour

### Content Storage

Page content lives under `content/pages/` as Markdown files with YAML frontmatter:

```
content/pages/
  _defaults/           # Sensible defaults for all pages
    privacy-policy.md
    terms-of-use.md
    disclaimer.md
    about.md
    landing.md
  stroke/              # Domain-specific overrides
    about.md
    landing.md
  neurology/
    about.md
    landing.md
```

Domain-specific content files are owned by their respective domain specs (e.g., `stroke-migration` owns `content/pages/stroke/`). Default content files are owned by this spec.

### Frontmatter Schema

Each page file uses this frontmatter:

```yaml
---
slug: "privacy-policy"       # WordPress URL slug (required)
title: "Privacy Policy"      # Page title (required)
status: "publish"            # "publish" or "draft" (default: "publish")
menu_order: 10               # Sort order for menus (default: 0)
---
```

### Content Resolution

When syncing pages for a domain, each slug in the `pages` list is resolved via:

1. `content/pages/{domain}/{slug}.md` — domain-specific override
2. `content/pages/_defaults/{slug}.md` — sensible default

If neither exists, log a warning and skip the slug.

### WordPress Configuration

`wp-config.yaml` gains a `pages` list declaring which pages to sync:

```yaml
pages:
  - privacy-policy
  - terms-of-use
  - disclaimer
  - about
  - landing
```

A domain only gets the pages it declares. No implicit pages.

### Sync Process

The sync module (`src/distribute/wp_pages.py`) performs these steps:

1. **Load config.** Read `wp-config.yaml` for the domain. Check preconditions (same as wp-publish: `enabled`, `site_url`, credentials).

2. **Load state.** Read `data/domains/{domain}/wp-pages-state.yaml` if it exists.

3. **For each slug in `config.pages`:**
   a. Resolve the content file via the override chain.
   b. Parse frontmatter and Markdown body.
   c. Compute SHA-256 of the resolved file contents.
   d. Compare to `content_sha` in state. If unchanged, skip (log at debug level).
   e. Render Markdown body to HTML.
   f. Look up existing page: `GET /wp-json/wp/v2/pages?slug={slug}`.
   g. If page exists: `POST /wp-json/wp/v2/pages/{id}` to update.
   h. If page does not exist: `POST /wp-json/wp/v2/pages` to create.
   i. Update state entry with `wp_page_id`, `content_sha`, and `last_synced` timestamp.

4. **Set front page.** If the `landing` slug was synced and has a `wp_page_id`, call `POST /wp-json/wp/v2/settings` with `{"show_on_front": "page", "page_on_front": <id>}`.

5. **Write state.** Save updated state to `data/domains/{domain}/wp-pages-state.yaml`.

### Markdown Rendering

Convert Markdown to HTML using Python's `markdown` library with the `extra` extension (for tables, fenced code blocks, etc.). Wrap the output in a `<!-- wp:html -->` block to prevent the WordPress block editor from mangling the HTML.

### Source of Truth

The repository is the strict source of truth. If a page is edited in the WordPress admin, the next sync overwrites it with the repo version. The sync logs a warning if the WordPress page's `modified` timestamp is newer than `last_synced`, but does not block.

### State File

```yaml
# data/domains/{domain}/wp-pages-state.yaml
pages:
  privacy-policy:
    wp_page_id: 42
    content_sha: "a1b2c3..."
    last_synced: "2026-04-04T10:00:00Z"
```

The state file is domain-scoped and gitignored (it contains WordPress IDs specific to each deployment).

### CLI Interface

```bash
# Sync all pages for a domain
python -m src.distribute.wp_pages --domain stroke

# Dry run — resolve and render but don't call API
python -m src.distribute.wp_pages --domain stroke --dry-run
```

### GitHub Actions

Each domain has its own workflow file (consistent with the one-workflow-per-domain convention used by `weekly-digest-*.yml`). Each triggers on pushes to `_defaults/` and its own domain directory:

```yaml
on:
  push:
    branches: [main]
    paths: ["content/pages/_defaults/**", "content/pages/{domain}/**"]
```

A change to `_defaults/` triggers all domain workflows (the page may be inherited). A change to a domain directory triggers only that domain's workflow.

### Error Handling

- Failed page create/update: log warning, continue to next page. Do not halt.
- Missing content file for a declared slug: log warning, skip.
- Failed front page setting: log warning, do not halt.
- State file missing: treat all pages as new (full sync).

## Decisions

| ID | Decision | Alternatives Considered | Rationale | Date |
|----|----------|------------------------|-----------|------|
| WPG1 | Markdown-in-repo with WP REST API sync | Git deploy to WordPress; theme templates; manual upload | Consistent with existing `wp_publish.py` pattern. Git-tracked, PR-reviewable. Works on any WP host including GoDaddy managed. | 2026-04-04 |
| WPG2 | Upsert semantics (create-or-update by slug) | Always create; delete-and-recreate | Pages are long-lived resources. Upsert preserves WordPress page IDs, comments, and SEO. | 2026-04-04 |
| WPG3 | SHA-based skip for unchanged content | Always push; timestamp comparison | SHA is deterministic and immune to clock skew. Avoids unnecessary API calls. | 2026-04-04 |
| WPG4 | Repo is strict source of truth, WP admin edits overwritten | WP admin editable; hybrid with merge | Matches project philosophy of version-controlled config. Advisory warning logged when WP was edited. Prevents config drift. | 2026-04-04 |
| WPG5 | All pages overridable by domains, no enforced shared pages | Shared pages locked, domain pages separate | Domains may have different legal jurisdictions, branding, or regulatory requirements. Defaults are sensible; overrides are intentional. | 2026-04-04 |
| WPG6 | `<!-- wp:html -->` wrapper for rendered content | Raw HTML; Gutenberg blocks; classic editor only | Prevents Gutenberg from parsing and mangling the HTML. Works regardless of editor mode. | 2026-04-04 |
| WPG7 | Standalone sync script, not part of weekly pipeline | Part of main pipeline; manual only | Content editors shouldn't wait for the weekly article run. Triggered by content file changes via GitHub Actions. | 2026-04-04 |

## Tests

### Unit Tests

- **test_resolve_page_content_domain_override**: Given a slug with both `_defaults/` and `{domain}/` versions, verify the domain version is returned.
- **test_resolve_page_content_default_fallback**: Given a slug with only a `_defaults/` version, verify the default is returned.
- **test_resolve_page_content_missing**: Given a slug with no file, verify None is returned.
- **test_parse_frontmatter**: Verify YAML frontmatter is parsed into slug, title, status, menu_order fields.
- **test_render_markdown_to_html**: Verify Markdown is converted to HTML and wrapped in `<!-- wp:html -->` block.
- **test_sha_unchanged_skips_sync**: Given a state entry with matching SHA, verify no API call is made.
- **test_sha_changed_triggers_sync**: Given a state entry with different SHA, verify an update API call is made.
- **test_new_page_creates**: Given no state entry and no existing WP page, verify a create API call is made.
- **test_existing_page_updates**: Given no state entry but an existing WP page found by slug, verify an update API call is made.
- **test_front_page_setting**: After syncing a `landing` page, verify the settings API is called with correct page ID.
- **test_dry_run_no_api_calls**: With `--dry-run`, verify no HTTP requests are made but content is resolved and rendered.
- **test_skip_when_disabled**: When `enabled: false`, verify no API calls.
- **test_skip_when_no_credentials**: When env vars unset, verify no API calls.

### Contract Tests

- **test_config_pages_field**: Verify `wp-config.yaml` with `pages` list deserializes into `WordPressConfig` with correct page slugs.

### Integration Tests

- **test_sync_real_page**: Create/update a test page on a real WordPress site. (Requires credentials; skip in CI if unavailable.)

## Environment Requirements

- WordPress 6.0+ with REST API enabled
- SSL certificate
- `pubmed-pipeline.php` plugin activated (for meta fields; pages use core WP endpoints)
- Environment variables: `WP_USERNAME`, `WP_APP_PASSWORD`
- Python `markdown` library (add to `requirements.txt`)

## Implementation Notes

- Reuse `_build_auth_header()` from `wp_publish.py` — extract to a shared utility or import directly.
- The `data/domains/{domain}/` directory already exists for `seen-pmids.json`. State file follows the same convention.
- Page content files use the same Markdown + YAML frontmatter convention as blog templates in `config/templates/`.
- The `markdown` library is a pure-Python dependency with no native extensions.
