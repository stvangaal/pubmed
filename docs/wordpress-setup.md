# WordPress Setup Guide

This guide covers setting up a WordPress site to receive article posts from the PubMed pipeline and serve as a member portal with topic-filtered email digests.

## Architecture

```
Pipeline (GitHub Actions) ──POST──> WordPress REST API (articles as posts)
                                          │
                                    WordPress Site
                                    ├── Posts (articles with clinical topic taxonomy)
                                    ├── Ultimate Member (signup, login, profile)
                                    └── Custom REST endpoint (/digest/v1/members)
                                          │
Member Digest Script (GitHub Actions) ──GET──> members + posts
                                    └── Resend API (per-member filtered emails)
```

## 1. WordPress Installation

**Recommended**: Managed WordPress hosting (e.g., SiteGround, Bluehost, or WordPress.com Business plan) for automatic updates and SSL.

**Minimum requirements**:
- WordPress 6.0+
- PHP 8.0+
- SSL certificate (required for REST API authentication)

## 2. Install Ultimate Member Plugin

1. Go to **Plugins > Add New** in the WordPress admin
2. Search for "Ultimate Member"
3. Install and activate **Ultimate Member** (by Starter Sites)
4. Run the setup wizard when prompted — it creates the required pages (Login, Register, Account, etc.)

### Configure Custom Profile Field

1. Go to **Ultimate Member > Forms > Default Registration**
2. Click the form builder, then add a new field:
   - **Field type**: Checkbox
   - **Field title**: Clinical Topics
   - **Meta key**: `clinical_topics`
   - **Options** (one per line):
     ```
     Acute Treatment
     Prevention
     Rehabilitation
     Hospital Care
     Imaging
     Epidemiology
     ```
   - Adjust options to match your domain's `summary-config.yaml` subdomain_options
3. Save the form
4. Optionally add the same field to the **Profile** form so members can update preferences later

## 3. Register Custom Taxonomy

Add to your theme's `functions.php` or create a micro-plugin:

```php
<?php
/**
 * Register Clinical Topics taxonomy for article posts.
 */
add_action('init', function () {
    register_taxonomy('clinical_topics', 'post', [
        'label'        => 'Clinical Topics',
        'public'       => true,
        'hierarchical' => false,
        'show_in_rest' => true,  // Required for REST API access
        'rest_base'    => 'clinical_topics',
    ]);
});
```

## 4. Register Article Meta Fields

Expose custom post meta fields via the REST API:

```php
<?php
/**
 * Register article meta fields for REST API access.
 */
add_action('init', function () {
    $meta_fields = [
        'pmid'         => 'string',
        'triage_score' => 'string',
        'journal'      => 'string',
        'pub_date'     => 'string',
        'source_topic' => 'string',
        'preindex'     => 'string',
    ];

    foreach ($meta_fields as $key => $type) {
        register_post_meta('post', $key, [
            'show_in_rest'  => true,
            'single'        => true,
            'type'          => $type,
            'auth_callback' => function () {
                return current_user_can('edit_posts');
            },
        ]);
    }
});
```

## 5. Custom REST Endpoint for Member Preferences

This endpoint allows the external digest script to fetch member emails and topic preferences.

```php
<?php
/**
 * Custom REST endpoint: GET /wp-json/digest/v1/members
 *
 * Returns registered members with their clinical topic preferences.
 * Protected by a shared secret (WP_DIGEST_API_SECRET constant).
 */
add_action('rest_api_init', function () {
    register_rest_route('digest/v1', '/members', [
        'methods'             => 'GET',
        'callback'            => 'digest_get_members',
        'permission_callback' => 'digest_verify_secret',
    ]);
});

function digest_verify_secret(WP_REST_Request $request): bool {
    $expected = defined('WP_DIGEST_API_SECRET') ? WP_DIGEST_API_SECRET : '';
    if (!$expected) {
        return false;  // Secret not configured — deny all access
    }
    return $request->get_header('X-Digest-Secret') === $expected;
}

function digest_get_members(): WP_REST_Response {
    $users = get_users(['role__in' => ['subscriber', 'um_member']]);
    $members = [];

    foreach ($users as $user) {
        $topics_raw = get_user_meta($user->ID, 'clinical_topics', true);
        $topics = is_array($topics_raw) ? $topics_raw : [];

        $members[] = [
            'email'        => $user->user_email,
            'display_name' => $user->display_name,
            'topics'       => array_values($topics),
        ];
    }

    return new WP_REST_Response($members, 200);
}
```

Add the shared secret to `wp-config.php`:

```php
define('WP_DIGEST_API_SECRET', 'your-random-secret-here');
```

## 6. Application Password for Pipeline

The pipeline uses WordPress Application Passwords to authenticate POST requests.

1. Go to **Users > Profile** in WordPress admin
2. Scroll to **Application Passwords**
3. Enter a name (e.g., "PubMed Pipeline") and click **Add New**
4. Copy the generated password (shown once)

## 7. Environment Variables

Each domain has its own WordPress site and credentials. The env var names are declared in the domain's `wp-config.yaml` and follow the pattern `WP_{DOMAIN}_{PURPOSE}`.

Set these in your GitHub Actions secrets:

| Variable pattern | Purpose | Where to get it |
|----------|---------|-----------------|
| `WP_{DOMAIN}_USERNAME` | WordPress username for API auth | Your WordPress admin username |
| `WP_{DOMAIN}_APP_PASSWORD` | Application Password | Generated in step 6 |
| `WP_{DOMAIN}_DIGEST_SECRET` | Shared secret for member endpoint | Must match `WP_DIGEST_API_SECRET` in wp-config.php |

Example for the stroke domain:

| Variable | Value |
|----------|-------|
| `WP_STROKE_USERNAME` | WordPress admin username for strokeconversations.ca |
| `WP_STROKE_APP_PASSWORD` | Application Password generated in step 6 |
| `WP_STROKE_DIGEST_SECRET` | Shared secret matching wp-config.php |

## 8. Domain Config

Edit `config/domains/<domain>/wp-config.yaml`:

```yaml
config_version: 1
enabled: true
site_url: "https://your-site.com"
clinical_topics_taxonomy: "clinical_topics"

# Environment variable names for this domain's credentials.
env_username: "WP_YOURDOMAIN_USERNAME"
env_app_password: "WP_YOURDOMAIN_APP_PASSWORD"
env_digest_secret: "WP_YOURDOMAIN_DIGEST_SECRET"

# Meta fields the pipeline plugin should expose via REST API.
expected_meta_fields:
  - pmid
  - triage_score
  - journal
  - pub_date
  - source_topic
  - preindex
```

## 9. Verify Setup

### Automated Connection Tests

The project includes live connection tests that verify each WordPress site is properly configured:

```bash
# Run read-only checks against a specific domain
WP_STROKE_USERNAME="admin" WP_STROKE_APP_PASSWORD="xxxx xxxx xxxx xxxx" \
  pytest -m live -k stroke -v

# Include the digest endpoint test
WP_STROKE_DIGEST_SECRET="your-secret" \
  pytest -m live -k stroke -v

# Include the post create/delete lifecycle test
pytest -m "live or live_write" -k stroke -v
```

The tests check: REST API reachability, taxonomy registration, meta field schema, authentication, members endpoint, and (with `live_write`) post creation and deletion.

### Manual Verification

```bash
# Test article upload
export WP_STROKE_USERNAME="admin"
export WP_STROKE_APP_PASSWORD="xxxx xxxx xxxx xxxx"
python3 -m src.pipeline --domain stroke --test

# Test member endpoint
curl -H "X-Digest-Secret: your-secret" https://your-site.com/wp-json/digest/v1/members

# Test member digest
export WP_STROKE_DIGEST_SECRET="your-secret"
export RESEND_API_KEY="re_xxxxx"
python3 -m src.distribute.wp_digest --domain stroke --days 7
```
