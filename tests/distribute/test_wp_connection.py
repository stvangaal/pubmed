# owner: wp-publish
"""Live connection tests for WordPress site configuration.

Run with:
    pytest -m live                          # read-only checks, all domains
    pytest -m "live or live_write"          # includes post create/delete
    pytest -m live -k stroke                # single domain

Requires domain-scoped env vars (e.g. WP_STROKE_USERNAME, WP_STROKE_APP_PASSWORD).
"""

import httpx
import pytest

from src.distribute.wp_publish import _build_auth_header

from tests.distribute.conftest import (
    skip_if_no_credentials,
    skip_if_no_digest_secret,
    skip_if_not_configured,
)


@pytest.mark.live
class TestWpApiReachable:
    """Verify the WordPress REST API is reachable and responds."""

    def test_rest_api_root(self, wp_config):
        skip_if_not_configured(wp_config)
        url = f"{wp_config.site_url.rstrip('/')}/wp-json/"
        resp = httpx.get(url, timeout=15)
        assert resp.status_code == 200
        data = resp.json()
        assert "namespaces" in data

    def test_wp_v2_namespace_present(self, wp_config):
        skip_if_not_configured(wp_config)
        url = f"{wp_config.site_url.rstrip('/')}/wp-json/"
        resp = httpx.get(url, timeout=15)
        data = resp.json()
        assert "wp/v2" in data["namespaces"]


@pytest.mark.live
class TestClinicalTopicsTaxonomy:
    """Verify the clinical_topics taxonomy is registered and REST-accessible."""

    def test_taxonomy_endpoint_exists(self, wp_config, wp_credentials):
        skip_if_not_configured(wp_config)
        auth = _build_auth_header(*wp_credentials)
        url = (
            f"{wp_config.site_url.rstrip('/')}/wp-json/wp/v2"
            f"/{wp_config.clinical_topics_taxonomy}"
        )
        resp = httpx.get(url, headers={"Authorization": auth}, timeout=15)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_taxonomy_in_discovery(self, wp_config, wp_credentials):
        skip_if_not_configured(wp_config)
        auth = _build_auth_header(*wp_credentials)
        url = (
            f"{wp_config.site_url.rstrip('/')}/wp-json/wp/v2"
            f"/taxonomies/{wp_config.clinical_topics_taxonomy}"
        )
        resp = httpx.get(url, headers={"Authorization": auth}, timeout=15)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("rest_base") == wp_config.clinical_topics_taxonomy


@pytest.mark.live
class TestArticleMetaFields:
    """Verify article meta fields are registered and visible in the REST schema."""

    def test_post_schema_has_meta_fields(self, wp_config, wp_credentials):
        skip_if_not_configured(wp_config)
        if not wp_config.expected_meta_fields:
            pytest.skip("No expected_meta_fields configured for this domain")
        auth = _build_auth_header(*wp_credentials)
        url = f"{wp_config.site_url.rstrip('/')}/wp-json/wp/v2/posts"
        resp = httpx.options(url, headers={"Authorization": auth}, timeout=15)
        assert resp.status_code == 200
        schema = resp.json()
        meta_properties = (
            schema.get("schema", {})
            .get("properties", {})
            .get("meta", {})
            .get("properties", {})
        )
        for field_name in wp_config.expected_meta_fields:
            assert field_name in meta_properties, (
                f"Meta field '{field_name}' not in post schema"
            )


@pytest.mark.live
class TestAuthentication:
    """Verify Application Passwords authentication works."""

    def test_authenticated_request_succeeds(self, wp_config, wp_credentials):
        skip_if_not_configured(wp_config)
        auth = _build_auth_header(*wp_credentials)
        url = f"{wp_config.site_url.rstrip('/')}/wp-json/wp/v2/users/me"
        resp = httpx.get(url, headers={"Authorization": auth}, timeout=15)
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert "name" in data

    def test_unauthenticated_cannot_create_post(self, wp_config):
        skip_if_not_configured(wp_config)
        url = f"{wp_config.site_url.rstrip('/')}/wp-json/wp/v2/posts"
        resp = httpx.post(url, json={"title": "should-fail"}, timeout=15)
        assert resp.status_code == 401


@pytest.mark.live
class TestDigestMembersEndpoint:
    """Verify the custom digest/v1/members endpoint exists."""

    def test_members_endpoint_returns_200(self, wp_config, digest_api_secret):
        skip_if_not_configured(wp_config)
        url = f"{wp_config.site_url.rstrip('/')}/wp-json/digest/v1/members"
        resp = httpx.get(
            url,
            headers={"X-Digest-Secret": digest_api_secret},
            timeout=15,
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_members_endpoint_rejects_bad_secret(self, wp_config):
        skip_if_not_configured(wp_config)
        skip_if_no_credentials(wp_config)
        url = f"{wp_config.site_url.rstrip('/')}/wp-json/digest/v1/members"
        resp = httpx.get(
            url,
            headers={"X-Digest-Secret": "wrong-secret-value"},
            timeout=15,
        )
        assert resp.status_code in (401, 403)

    def test_digest_namespace_in_discovery(self, wp_config):
        skip_if_not_configured(wp_config)
        skip_if_no_credentials(wp_config)
        url = f"{wp_config.site_url.rstrip('/')}/wp-json/"
        resp = httpx.get(url, timeout=15)
        data = resp.json()
        assert "digest/v1" in data.get("namespaces", [])


@pytest.mark.live
@pytest.mark.live_write
class TestPostLifecycle:
    """Create a test post, verify it, then delete it."""

    def test_create_and_delete_post(self, wp_config, wp_credentials):
        skip_if_not_configured(wp_config)
        auth = _build_auth_header(*wp_credentials)
        headers = {"Authorization": auth, "Content-Type": "application/json"}
        api_base = f"{wp_config.site_url.rstrip('/')}/wp-json/wp/v2"

        # Build meta from expected fields if available
        meta = {}
        field_test_values = {
            "pmid": "TEST-00000",
            "triage_score": "0.99",
            "journal": "Test Journal",
            "pub_date": "2026-01-01",
            "source_topic": "test",
            "preindex": "false",
        }
        for field_name in wp_config.expected_meta_fields:
            meta[field_name] = field_test_values.get(field_name, "test-value")

        post_data = {
            "title": "[TEST] Pipeline Connection Test — safe to delete",
            "content": "<p>Automated connection test. This post should be deleted.</p>",
            "status": "draft",
            "meta": meta,
        }

        create_resp = httpx.post(
            f"{api_base}/posts", json=post_data, headers=headers, timeout=30
        )
        assert create_resp.status_code == 201, (
            f"Post creation failed: {create_resp.text}"
        )
        post_id = create_resp.json()["id"]

        try:
            # Verify meta fields persisted
            get_resp = httpx.get(
                f"{api_base}/posts/{post_id}", headers=headers, timeout=15
            )
            assert get_resp.status_code == 200
            returned_meta = get_resp.json().get("meta", {})
            for field_name, expected_value in meta.items():
                assert returned_meta.get(field_name) == expected_value, (
                    f"Meta field '{field_name}': expected {expected_value!r}, "
                    f"got {returned_meta.get(field_name)!r}"
                )
        finally:
            # Always clean up — force=true bypasses trash
            delete_resp = httpx.delete(
                f"{api_base}/posts/{post_id}",
                params={"force": "true"},
                headers=headers,
                timeout=15,
            )
            assert delete_resp.status_code == 200
