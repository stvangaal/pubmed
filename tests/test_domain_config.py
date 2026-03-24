# owner: domain-config
"""Tests for domain-scoped config infrastructure."""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from src.config import (
    CURRENT_DOMAIN_SCHEMA_VERSION,
    _config_path,
    check_domain_schema,
    load_search_config,
    load_filter_config,
    load_summary_config,
    load_distribute_config,
    load_blog_config,
    load_email_config,
)


# --- Template completeness ---


TEMPLATE_DIR = Path("config/domains/_template")
STROKE_DIR = Path("config/domains/stroke")

EXPECTED_YAMLS = [
    "domain.yaml",
    "search-config.yaml",
    "filter-config.yaml",
    "summary-config.yaml",
    "distribute-config.yaml",
    "blog-config.yaml",
    "email-config.yaml",
]

EXPECTED_PROMPTS = [
    "prompts/triage-prompt.md",
    "prompts/summary-prompt.md",
]


class TestTemplateCompleteness:
    """Verify the _template directory is complete and well-formed."""

    @pytest.mark.parametrize("filename", EXPECTED_YAMLS + EXPECTED_PROMPTS)
    def test_template_file_exists(self, filename):
        assert (TEMPLATE_DIR / filename).exists(), f"Missing template file: {filename}"

    @pytest.mark.parametrize("filename", [f for f in EXPECTED_YAMLS if f != "domain.yaml"] + EXPECTED_PROMPTS)
    def test_template_has_todo(self, filename):
        content = (TEMPLATE_DIR / filename).read_text()
        assert "TODO" in content, f"Template {filename} should contain TODO markers"

    def test_domain_yaml_schema_version(self):
        data = yaml.safe_load((TEMPLATE_DIR / "domain.yaml").read_text())
        assert data["schema_version"] == CURRENT_DOMAIN_SCHEMA_VERSION

    def test_changelog_exists(self):
        assert Path("config/domains/CHANGELOG.md").exists()

    def test_changelog_documents_version_1(self):
        content = Path("config/domains/CHANGELOG.md").read_text()
        assert "Version 1" in content


# --- Stroke domain completeness ---


class TestStrokeDomainCompleteness:
    """Verify the stroke domain directory is complete and has no TODOs."""

    @pytest.mark.parametrize("filename", EXPECTED_YAMLS + EXPECTED_PROMPTS)
    def test_stroke_file_exists(self, filename):
        assert (STROKE_DIR / filename).exists(), f"Missing stroke file: {filename}"

    @pytest.mark.parametrize("filename", EXPECTED_YAMLS)
    def test_stroke_yaml_no_todo(self, filename):
        content = (STROKE_DIR / filename).read_text()
        assert "TODO" not in content, f"Stroke {filename} should not contain TODO markers"

    def test_stroke_schema_version_matches(self):
        data = yaml.safe_load((STROKE_DIR / "domain.yaml").read_text())
        assert data["schema_version"] == CURRENT_DOMAIN_SCHEMA_VERSION

    def test_stroke_seen_pmids_path_is_domain_scoped(self):
        data = yaml.safe_load((STROKE_DIR / "filter-config.yaml").read_text())
        path = data["llm_triage"]["seen_pmids_file"]
        assert "domains/stroke" in path

    def test_stroke_output_path_is_domain_scoped(self):
        data = yaml.safe_load((STROKE_DIR / "distribute-config.yaml").read_text())
        assert "domains/stroke" in data["output"]["file"]

    def test_stroke_digests_dir_is_domain_scoped(self):
        data = yaml.safe_load((STROKE_DIR / "blog-config.yaml").read_text())
        assert data["digests_dir"] == "digests/stroke"

    def test_stroke_triage_prompt_path_is_domain_scoped(self):
        data = yaml.safe_load((STROKE_DIR / "filter-config.yaml").read_text())
        path = data["llm_triage"]["triage_prompt_file"]
        assert "domains/stroke" in path
        assert Path(path).exists()

    def test_stroke_summary_prompt_path_is_domain_scoped(self):
        data = yaml.safe_load((STROKE_DIR / "summary-config.yaml").read_text())
        path = data["prompt_template_file"]
        assert "domains/stroke" in path
        assert Path(path).exists()


# --- Config path resolution ---


class TestConfigPath:
    """Verify _config_path resolves correctly for domain and legacy modes."""

    def test_domain_scoped_path(self):
        result = _config_path("search-config.yaml", "stroke")
        assert result == "config/domains/stroke/search-config.yaml"

    def test_legacy_flat_path(self):
        result = _config_path("search-config.yaml", None)
        assert result == "config/search-config.yaml"

    def test_domain_scoped_path_other_domain(self):
        result = _config_path("filter-config.yaml", "neurology")
        assert result == "config/domains/neurology/filter-config.yaml"


# --- Schema version check ---


class TestSchemaCheck:
    """Verify check_domain_schema warns appropriately."""

    def test_matching_version_no_warning(self, caplog):
        with caplog.at_level(logging.WARNING):
            check_domain_schema("stroke")
        assert "schema_version" not in caplog.text.lower() or "warning" not in caplog.text.lower()

    def test_mismatched_version_warns(self, tmp_path, caplog):
        domain_dir = tmp_path / "config" / "domains" / "testdomain"
        domain_dir.mkdir(parents=True)
        (domain_dir / "domain.yaml").write_text('schema_version: "999"')

        with patch("src.config.Path") as mock_path:
            # Make Path(manifest_path).exists() return True and open the tmp file
            pass

        # Simpler: test with a real mismatched domain.yaml
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as td:
            domain_path = Path(td) / "domain.yaml"
            domain_path.write_text('schema_version: "999"')

            with patch("src.config._load_yaml", return_value={"schema_version": "999"}):
                with patch("pathlib.Path.exists", return_value=True):
                    with caplog.at_level(logging.WARNING):
                        check_domain_schema("testdomain")
                    assert "999" in caplog.text

    def test_missing_manifest_warns(self, caplog):
        with caplog.at_level(logging.WARNING):
            check_domain_schema("nonexistent_domain_xyz")
        assert "no domain.yaml" in caplog.text.lower() or "schema version unknown" in caplog.text.lower()


# --- Config loaders with domain ---


class TestDomainConfigLoading:
    """Verify all config loaders work with --domain stroke."""

    def test_load_search_config_domain(self):
        config = load_search_config(domain="stroke")
        assert "stroke" in config.mesh_terms

    def test_load_filter_config_domain(self):
        config = load_filter_config(domain="stroke")
        assert config.llm_triage.score_threshold == 0.70
        assert "domains/stroke" in config.llm_triage.seen_pmids_file

    def test_load_summary_config_domain(self):
        config = load_summary_config(domain="stroke")
        assert "Acute Treatment" in config.subdomain_options

    def test_load_distribute_config_domain(self):
        config = load_distribute_config(domain="stroke")
        assert "domains/stroke" in config.output.file

    def test_load_blog_config_domain(self):
        config = load_blog_config(domain="stroke")
        assert config.digests_dir == "digests/stroke"

    def test_load_email_config_domain(self):
        config = load_email_config(domain="stroke")
        assert config.enabled is True
        assert "strokedigest" in config.from_address

    def test_load_search_config_legacy(self):
        """Legacy mode (no domain) still works."""
        config = load_search_config()
        assert "stroke" in config.mesh_terms
