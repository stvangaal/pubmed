# owner: project-infrastructure
"""Load pipeline configuration from YAML files."""

import logging
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

# Bump this when any domain config schema change requires operator action.
# See config/domains/CHANGELOG.md for migration notes.
CURRENT_DOMAIN_SCHEMA_VERSION = "1"

from src.models import (
    SearchConfig,
    FilterConfig,
    RuleFilterConfig,
    LLMTriageConfig,
    SummaryConfig,
    DistributeConfig,
    OutputConfig,
    BlogConfig,
    BlogTemplatesConfig,
    EmailConfig,
)


def check_domain_schema(domain: str) -> None:
    """Warn if the domain's schema_version doesn't match CURRENT_DOMAIN_SCHEMA_VERSION.

    Non-fatal — the pipeline continues, but operators should migrate the config.
    See config/domains/CHANGELOG.md for migration notes.
    """
    manifest_path = f"config/domains/{domain}/domain.yaml"
    if not Path(manifest_path).exists():
        logger.warning(
            "Domain '%s' has no domain.yaml — schema version unknown. "
            "Copy config/domains/_template/domain.yaml into your domain directory.",
            domain,
        )
        return

    data = _load_yaml(manifest_path)
    found = str(data.get("schema_version", "")).strip()
    if found != CURRENT_DOMAIN_SCHEMA_VERSION:
        logger.warning(
            "Domain '%s' config schema_version '%s' != current '%s'. "
            "See config/domains/CHANGELOG.md for migration steps.",
            domain,
            found or "(missing)",
            CURRENT_DOMAIN_SCHEMA_VERSION,
        )


def _load_yaml(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _config_path(filename: str, domain: str | None) -> str:
    """Resolve config file path for flat or domain-scoped layout."""
    if domain:
        return f"config/domains/{domain}/{filename}"
    return f"config/{filename}"


def load_search_config(
    path: str | None = None,
    domain: str | None = None,
) -> SearchConfig:
    resolved = path or _config_path("search-config.yaml", domain)
    data = _load_yaml(resolved)
    return SearchConfig(**data)


def load_filter_config(
    path: str | None = None,
    domain: str | None = None,
) -> FilterConfig:
    resolved = path or _config_path("filter-config.yaml", domain)
    data = _load_yaml(resolved)
    return FilterConfig(
        rule_filter=RuleFilterConfig(**data.get("rule_filter", {})),
        llm_triage=LLMTriageConfig(**data.get("llm_triage", {})),
        priority_journals=data.get("priority_journals", []),
    )


def load_summary_config(
    path: str | None = None,
    domain: str | None = None,
) -> SummaryConfig:
    resolved = path or _config_path("summary-config.yaml", domain)
    data = _load_yaml(resolved)
    # Load prompt template from file if prompt_template_file is specified
    if "prompt_template_file" in data:
        template_path = data.pop("prompt_template_file")
        with open(template_path) as f:
            data["prompt_template"] = f.read()
    return SummaryConfig(**data)


def load_distribute_config(
    path: str | None = None,
    domain: str | None = None,
) -> DistributeConfig:
    resolved = path or _config_path("distribute-config.yaml", domain)
    data = _load_yaml(resolved)
    output_data = data.pop("output", {})
    return DistributeConfig(
        output=OutputConfig(**output_data),
        **data,
    )


def load_email_config(
    path: str | None = None,
    domain: str | None = None,
) -> EmailConfig:
    resolved = path or _config_path("email-config.yaml", domain)
    data = _load_yaml(resolved)
    return EmailConfig(**data)


def load_blog_config(
    path: str | None = None,
    domain: str | None = None,
) -> BlogConfig:
    resolved = path or _config_path("blog-config.yaml", domain)
    data = _load_yaml(resolved)
    templates_data = data.pop("templates", {})
    return BlogConfig(
        templates=BlogTemplatesConfig(**templates_data),
        **data,
    )
