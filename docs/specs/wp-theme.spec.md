---
name: wp-theme
status: draft
owner: distribute
owns:
  - wordpress/theme/style.css
  - wordpress/theme/functions.php
  - wordpress/theme/templates/page-weekly-archive.php
  - wordpress/theme/templates/page-taxonomy-browse.php
  - wordpress/theme/templates/taxonomy.php
  - wordpress/theme/templates/single.php
  - wordpress/theme/css/archive-styles.css
requires:
  - name: wp-config
    version: v0
provides: []
---

# WordPress Theme

## Status
draft

## Target Phase
Phase 3

## Purpose
Provide a reusable GeneratePress child theme that gives members two archival browsing experiences — weekly digest view and clinical topic/condition browse — across all pipeline domains. The child theme is domain-agnostic: taxonomy slugs, meta fields, and branding are read from WordPress configuration (registered by the `pubmed-pipeline.php` plugin), not hardcoded. Each domain's WordPress site receives the same child theme files.

## Architecture

```
+-----------------------------------------------------------------------+
|                         WordPress Site (per domain)                    |
|                                                                       |
|  +---------------------------+   +------------------------------+     |
|  |   GeneratePress (parent)  |   |  pubmed-pipeline.php         |     |
|  |   - Base styles           |   |  - Registers taxonomies      |     |
|  |   - Layout engine         |   |    (clinical_topics,         |     |
|  |   - Nav + search icon     |   |     conditions)              |     |
|  +------------+--------------+   |  - Registers meta fields     |     |
|               |                  |    (pmid, triage_score,       |     |
|               | inherits         |     journal, pub_date,        |     |
|               v                  |     source_topic, preindex,   |     |
|  +---------------------------+   |     summary_short)            |     |
|  |   generatepress-child     |   |  - Members REST endpoint     |     |
|  |                           |   +------------------------------+     |
|  |  style.css                |                                        |
|  |  functions.php            |   +------------------------------+     |
|  |  css/archive-styles.css   |   |  Ultimate Member             |     |
|  |                           |   |  - Membership / login        |     |
|  |  templates/               |   |  - Menu visibility control   |     |
|  |  +----------------------+ |   |  - Access control (global)   |     |
|  |  | page-weekly-archive  | |   +------------------------------+     |
|  |  | page-taxonomy-browse | |                                        |
|  |  | taxonomy             | |                                        |
|  |  | single               | |                                        |
|  |  +----------------------+ |                                        |
|  +---------------------------+                                        |
+-----------------------------------------------------------------------+

User Flows:

  Logged-out visitor                    Logged-in member
  ==================                    ================

  Landing Page                          Landing Page
       |                                     |
       v                                     v
  [About] [Privacy] [Disclaimer]        [Archive] [Browse] [Account]
  [Contact] [Login] [Register]          [About] [Privacy] [Search]
       |                                     |
       v                                     +--------+---------+
  Login / Register                           |        |         |
       |                                     v        v         v
       +---> becomes member --->        /archive/  /browse/   Search
                                           |        |
                                           v        v
                                     ?week=...   /clinical_topics/X/
                                        |        /conditions/Y/
                                        v             |
                                     TOC + Full       v
                                     Summaries    Paginated post list
                                        |             |
                                        v             v
                                     Single Post <----+
                                     (full summary + taxonomy tags)
```

## Requires (Inbound Contracts)

| Dependency | Source | Definition |
|------------|--------|------------|
| WordPress configuration | user config | `wp-config` v0 |
| Published posts with meta | wp-publish | Posts with `clinical_topics`, `conditions` taxonomies and meta fields |
| `summary_short` meta field | wp-publish (new) | 2-sentence teaser stored as post meta |

## Provides (Outbound Contracts)

None — the theme is the final presentation layer.

## Behaviour

### Child Theme Files

All files live in the repository under `wordpress/theme/` and are deployed to `wp-content/themes/generatepress-child/` on each WordPress site. The child theme inherits all GeneratePress styling and only adds archive-specific templates and a small stylesheet.

```
wordpress/theme/
  style.css                            # Child theme declaration (Template: generatepress)
  functions.php                        # Register page templates, display custom taxonomies on posts, enqueue styles
  templates/
    page-weekly-archive.php            # Weekly digest index + detail view
    page-taxonomy-browse.php           # Combined clinical topics + conditions tag cloud
    taxonomy.php                       # Customized taxonomy archive (paginated post list)
    single.php                         # Single post with taxonomy tags
  css/
    archive-styles.css                 # Minimal custom styles for archive views
```

### Weekly Digest Archive

A single page template (`page-weekly-archive.php`) provides two views, toggled by the presence of a `week` query parameter.

#### Index View (`/archive/`)

- Queries all published posts, groups them by publish week (Monday–Sunday)
- Displays a reverse-chronological list of weeks, each showing:
  - Week heading (e.g., "April 1–7, 2026")
  - Article count for that week
  - Link to the detail view (`/archive/?week=2026-04-07`)
- Paginated (10 weeks per page)

#### Detail View (`/archive/?week=2026-04-07`)

- The `week` parameter is an ISO date; the template computes the Monday–Sunday range containing that date
- Queries posts published within that date range, ordered by `triage_score` meta field (descending)
- **Table of contents** at the top:
  - Each entry: article title (linked to anchor below) + `summary_short` meta field (2-sentence teaser)
- **Full summaries** below:
  - Each post's content rendered via `the_content()` (the HTML already published by `wp_publish.py`)
  - Anchor per article (`<a id="post-{ID}"></a>`) matching the TOC links
- Back link to the index view

#### Week Calculation

Given a date, compute the Monday of that week and the following Sunday. Query posts with `post_date` within that range. This uses PHP's `DateTime` with `modify('monday this week')` / `modify('sunday this week')`.

### Taxonomy Browse Page

A page template (`page-taxonomy-browse.php`) at `/browse/`:

- **Clinical Topics** section: queries all `clinical_topics` terms that have at least one published post. Displays each as a clickable tag showing term name and post count (e.g., "Prevention (12)"). Links to the WordPress taxonomy archive URL (e.g., `/clinical_topics/prevention/`).
- **Conditions** section: same format for `conditions` terms. Links to e.g., `/conditions/atrial-fibrillation/`.
- Both sections use `get_terms()` with `hide_empty => true`.
- Taxonomy slugs are not hardcoded — the template reads the registered taxonomies associated with the `post` type and filters for `clinical_topics` and `conditions`. These slugs are registered by `pubmed-pipeline.php` and match the domain's `wp-config.yaml`.

### Taxonomy Archive Pages

A custom taxonomy archive template (`taxonomy.php`) handles both `clinical_topics` and `conditions` archives:

- Page heading: taxonomy term name (e.g., "Prevention" or "Atrial Fibrillation")
- Paginated list of posts (10 per page), each showing:
  - Post title (linked to full post)
  - Publish date
  - Journal name (from `journal` meta field)
  - `summary_short` (from meta field) as the excerpt
- Back link to `/browse/`

### Single Post View

A lightly customized single post template (`single.php`) that extends GeneratePress's default:

- Post title
- Post meta: publish date, journal (from meta)
- Clickable taxonomy tags: `clinical_topics` and `conditions` terms displayed as linked tags below the title, linking to their respective archive pages
- Post content rendered via `the_content()` (pipeline-published HTML)
- Previous/next post navigation

The taxonomy display is added via `functions.php` using `get_the_terms()` for each custom taxonomy, rendered as a comma-separated list of links.

### Search

WordPress built-in search. GeneratePress provides a nav search icon enabled via **Appearance > Customize > Layout > Header**. No custom code needed — the built-in search queries post titles and content, which contain all article information.

### Styling

`archive-styles.css` provides minimal custom styles:

- TOC layout on the weekly detail view (indented, with subtle borders)
- Tag/button appearance for the taxonomy browse page
- Consistent typography with GeneratePress defaults
- Responsive — works on mobile

The stylesheet is enqueued via `functions.php` using `wp_enqueue_style()`. No inline styles.

### Domain Agnosticism

The child theme contains zero domain-specific content:

- Taxonomy slugs: read dynamically from registered taxonomies (registered by `pubmed-pipeline.php`)
- Meta fields: accessed by key name (same across all domains, declared in each domain's `wp-config.yaml`)
- Site title/branding: inherited from WordPress Settings > General
- Clinical topic and condition names: come from the taxonomy terms created by the pipeline at publish time

Adding a new domain means: install GeneratePress + child theme + pipeline plugin on the new WordPress site. No theme file changes.

## Pipeline Changes (Cross-Spec)

These changes are owned by `wp-publish` but are required by this spec:

### New Meta Field: `summary_short`

1. **`pubmed-pipeline.php`**: Add `'summary_short' => 'string'` to the `$meta_fields` array.
2. **`wp_publish.py`**: Include `summary.summary_short` in the post meta dict when creating posts.
3. **`wp-config.yaml`** (all domains): Add `summary_short` to `expected_meta_fields`.
4. **`test_wp_connection.py`**: The existing parametrized meta field test will automatically cover it once the config is updated.

## WordPress Admin Configuration (Per Domain)

These are manual one-time setup steps, documented in `docs/wordpress-setup.md`:

1. Install and activate GeneratePress theme
2. Install and activate GeneratePress child theme (upload `wordpress/theme/` contents)
3. Enable nav search icon: **Appearance > Customize > Layout > Header**
4. Create menus with UM per-item visibility:
   - Public: About, Privacy Policy, Disclaimer, Contact Us
   - Logged In: Archive, Browse, Account, Logout
   - Logged Out: Login, Register
5. Configure UM global access: members-only default + whitelist public pages
6. Create two WordPress pages:
   - "Archive" — assign page template "Weekly Archive"
   - "Browse" — assign page template "Taxonomy Browse"

## Deployment

Manual upload to `wp-content/themes/generatepress-child/` on each WordPress site, same deployment method as `pubmed-pipeline.php`. The child theme files are version-controlled in the repository under `wordpress/theme/`.

Future consideration: a deploy script that rsyncs both plugin and theme files to each domain's WordPress site. Not in scope for this spec.

## Decisions

| ID | Decision | Alternatives Considered | Rationale | Date |
|----|----------|------------------------|-----------|------|
| WT1 | GeneratePress child theme | Twenty Twenty-Four block theme; custom theme from scratch | Classic theme enables UM menu visibility. GeneratePress is lightweight (10kb), 500K+ installs, 5/5 stars, professional aesthetic. Child theme preserves upgrade path. | 2026-04-07 |
| WT2 | Custom PHP page templates for archive views | Shortcode plugins (Display Posts); Block patterns with Query Loop; Static page content | Full control, no extra plugin dependencies, version-controllable, domain-agnostic. Shortcode plugins add dependencies; block patterns had friction with the Site Editor. | 2026-04-07 |
| WT3 | Posts grouped by publish date for weekly view | Custom "digest_week" taxonomy; single post per week | Publish date is already set by the pipeline. No additional taxonomy or meta needed. Individual posts preserved for topic browsing. | 2026-04-07 |
| WT4 | `summary_short` as post meta for TOC teasers | WordPress auto-excerpt (truncated content); manual excerpt field | Purpose-built 2-sentence teaser already generated by the LLM during summarization. More readable than truncation. Consistent across all views. | 2026-04-07 |
| WT5 | Domain-agnostic theme reading from registered taxonomies | Hardcoded taxonomy slugs; per-domain theme variants | Same theme files deployed to every domain. Taxonomy slugs registered by the pipeline plugin match each domain's wp-config.yaml. Zero per-domain customization. | 2026-04-07 |
| WT6 | WordPress built-in search via GeneratePress nav icon | Relevanssi plugin; custom search page; Algolia | Adequate for the expected volume (hundreds of posts per year). Searches titles and content. No additional plugins. Can upgrade to Relevanssi later if needed. | 2026-04-07 |
| WT7 | Combined clinical topics + conditions on one browse page | Separate pages per taxonomy; dropdown filters | Single page gives users a complete overview. Two sections are clear and scannable. Fewer pages to maintain. | 2026-04-07 |

## Tests

### Live Connection Tests

Extend the existing `test_wp_connection.py` parametrized test suite:

- **test_summary_short_meta_field**: Verify `summary_short` appears in the post schema `meta` object (covered automatically once `expected_meta_fields` is updated in config).

### Manual Verification Checklist

Per domain, after deployment:

- [ ] Child theme activates without errors
- [ ] Weekly archive index loads at `/archive/` and lists weeks
- [ ] Weekly archive detail loads with TOC and full summaries
- [ ] Taxonomy browse page loads at `/browse/` with both sections
- [ ] Clicking a clinical topic tag shows paginated post list
- [ ] Clicking a condition tag shows paginated post list
- [ ] Single post displays clinical_topics and conditions as clickable tags
- [ ] Nav search icon works and returns relevant results
- [ ] Menu visibility: logged-out users see only public items
- [ ] Menu visibility: logged-in users see archive, browse, account items
- [ ] UM access control: logged-out users redirected to login for gated pages

## Environment Requirements

- WordPress 6.0+ with REST API enabled
- GeneratePress theme installed and active
- `pubmed-pipeline.php` plugin activated (registers taxonomies and meta fields)
- Ultimate Member plugin activated (membership and access control)
- PHP 8.0+
