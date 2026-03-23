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
