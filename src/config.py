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
    Subscriber,
)


def _load_yaml(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_search_config(path: str = "config/search-config.yaml") -> SearchConfig:
    data = _load_yaml(path)
    return SearchConfig(**data)


def load_filter_config(path: str = "config/filter-config.yaml") -> FilterConfig:
    data = _load_yaml(path)
    return FilterConfig(
        rule_filter=RuleFilterConfig(**data.get("rule_filter", {})),
        llm_triage=LLMTriageConfig(**data.get("llm_triage", {})),
        priority_journals=data.get("priority_journals", []),
    )


def load_summary_config(path: str = "config/summary-config.yaml") -> SummaryConfig:
    data = _load_yaml(path)
    # Load prompt template from file if prompt_template_file is specified
    if "prompt_template_file" in data:
        template_path = data.pop("prompt_template_file")
        with open(template_path) as f:
            data["prompt_template"] = f.read()
    return SummaryConfig(**data)


def load_distribute_config(path: str = "config/distribute-config.yaml") -> DistributeConfig:
    data = _load_yaml(path)
    output_data = data.pop("output", {})
    return DistributeConfig(
        output=OutputConfig(**output_data),
        **data,
    )


def load_email_config(path: str = "config/email-config.yaml") -> EmailConfig:
    data = _load_yaml(path)
    return EmailConfig(**data)


def load_subscribers(
    path: str = "config/subscribers.yaml",
    email_config: EmailConfig | None = None,
) -> list[Subscriber]:
    """Load subscriber profiles from YAML.

    Falls back to email_config.to_addresses (universal digest for each)
    when the subscribers file does not exist.
    """
    config_path = Path(path)
    if config_path.exists():
        data = _load_yaml(path)
        entries = data.get("subscribers", [])
        return [
            Subscriber(
                email=entry["email"],
                name=entry.get("name", ""),
                subdomains=entry.get("subdomains", []),
            )
            for entry in entries
        ]

    # Fallback: synthesize from email-config.yaml to_addresses
    if email_config and email_config.to_addresses:
        return [Subscriber(email=addr) for addr in email_config.to_addresses]
    return []


def load_blog_config(path: str = "config/blog-config.yaml") -> BlogConfig:
    data = _load_yaml(path)
    templates_data = data.pop("templates", {})
    return BlogConfig(
        templates=BlogTemplatesConfig(**templates_data),
        **data,
    )
