# WordPress Config

## Status
draft

## Version
v0

## Description
Per-domain configuration for WordPress REST API integration. Controls whether articles are published to WordPress, which site to target, how to authenticate, and what plugin state to expect. Users edit this as a YAML file without touching source code.

## Schema

```yaml
# config/domains/<domain>/wp-config.yaml
config_version: 1

# Whether to upload articles to WordPress (set false to skip).
enabled: true

# WordPress site URL (no trailing slash).
site_url: "https://strokeconversations.ca"

# Slug of the custom taxonomy registered for clinical topics.
clinical_topics_taxonomy: "clinical_topics"

# Environment variable names for this domain's WordPress credentials.
env_username: "WP_STROKE_USERNAME"
env_app_password: "WP_STROKE_APP_PASSWORD"
env_digest_secret: "WP_STROKE_DIGEST_SECRET"

# Meta fields the pipeline plugin should expose via REST API.
expected_meta_fields:
  - pmid
  - triage_score
  - journal
  - pub_date
  - source_topic
  - preindex
```

```python
@dataclass
class WordPressConfig:
    enabled: bool                    # Whether to publish articles to WordPress
    site_url: str                    # WordPress site URL (no trailing slash)
    clinical_topics_taxonomy: str    # Taxonomy slug for clinical topics
    env_username: str                # Env var name for WordPress username
    env_app_password: str            # Env var name for Application Password
    env_digest_secret: str           # Env var name for digest API secret
    expected_meta_fields: list[str]  # Meta fields expected in REST API schema
```

## Domain Scoping

When `--domain` is specified, this config is loaded from `config/domains/{domain}/wp-config.yaml`. Each domain targets an independent WordPress site with its own credentials. The `env_*` fields declare environment variable names — the actual secrets are stored in GitHub Actions secrets and injected at runtime.

## Credential Naming Convention

Domain-scoped env vars follow the pattern `WP_{DOMAIN}_{PURPOSE}`:

| Domain | Username | App Password | Digest Secret |
|--------|----------|--------------|---------------|
| stroke | `WP_STROKE_USERNAME` | `WP_STROKE_APP_PASSWORD` | `WP_STROKE_DIGEST_SECRET` |
| neurology | `WP_NEUROLOGY_USERNAME` | `WP_NEUROLOGY_APP_PASSWORD` | `WP_NEUROLOGY_DIGEST_SECRET` |

## Constraints

- `site_url` must not have a trailing slash
- `site_url` must use HTTPS (required for Application Password auth)
- `clinical_topics_taxonomy` must match the taxonomy slug registered by the WordPress plugin
- `env_username` and `env_app_password` must name env vars that contain valid WordPress Application Password credentials
- `env_digest_secret` must name an env var matching the `WP_DIGEST_API_SECRET` constant in the site's `wp-config.php`
- `expected_meta_fields` should list all meta fields registered by the WordPress plugin; used by live connection tests

## Changelog

| Date | Version | Change | Affected Specs |
|------|---------|--------|----------------|
| 2026-03-30 | v0 | Initial draft — enabled, site_url, clinical_topics_taxonomy | wp-publish |
| 2026-04-04 | v0 | Added env_username, env_app_password, env_digest_secret, expected_meta_fields for domain-scoped credentials and live tests | wp-publish |
