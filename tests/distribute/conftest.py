# owner: wp-publish
"""Shared fixtures for WordPress integration tests."""

import os
from pathlib import Path

import pytest

from src.config import load_wp_config
from src.models import WordPressConfig


def _discover_wp_domains() -> list[str]:
    """Scan config/domains/ for directories containing wp-config.yaml."""
    domains_dir = Path("config/domains")
    domains = []
    for d in sorted(domains_dir.iterdir()):
        if d.name.startswith("_") or not d.is_dir():
            continue
        if (d / "wp-config.yaml").exists():
            domains.append(d.name)
    return domains


WP_DOMAINS = _discover_wp_domains()


@pytest.fixture(params=WP_DOMAINS)
def wp_domain(request) -> str:
    """Parametrized fixture yielding each discovered domain name."""
    return request.param


@pytest.fixture
def wp_config(wp_domain) -> WordPressConfig:
    """Load the WordPressConfig for the current domain."""
    return load_wp_config(domain=wp_domain)


def skip_if_not_configured(wp_config: WordPressConfig) -> None:
    """Skip the test if this domain's WP config has no usable URL."""
    if not wp_config.site_url or not wp_config.enabled:
        pytest.skip(
            f"WordPress not configured (enabled={wp_config.enabled}, "
            f"url={wp_config.site_url!r})"
        )


def skip_if_no_credentials(wp_config: WordPressConfig) -> None:
    """Skip if the domain's credential env vars are not set."""
    username = os.environ.get(wp_config.env_username)
    app_password = os.environ.get(wp_config.env_app_password)
    if not username or not app_password:
        pytest.skip(
            f"{wp_config.env_username} and/or {wp_config.env_app_password} not set"
        )


def skip_if_no_digest_secret(wp_config: WordPressConfig) -> None:
    """Skip if the domain's digest API secret env var is not set."""
    if not os.environ.get(wp_config.env_digest_secret):
        pytest.skip(f"{wp_config.env_digest_secret} not set")


@pytest.fixture
def wp_credentials(wp_config) -> tuple[str, str]:
    """Return (username, app_password) from domain-scoped env vars."""
    skip_if_not_configured(wp_config)
    skip_if_no_credentials(wp_config)
    return os.environ[wp_config.env_username], os.environ[wp_config.env_app_password]


@pytest.fixture
def digest_api_secret(wp_config) -> str:
    """Return the digest API secret from domain-scoped env var."""
    skip_if_not_configured(wp_config)
    skip_if_no_digest_secret(wp_config)
    return os.environ[wp_config.env_digest_secret]
