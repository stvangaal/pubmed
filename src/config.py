# owner: project-infrastructure
"""Load pipeline configuration from YAML files."""

import yaml
from pathlib import Path

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
