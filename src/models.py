# owner: project-infrastructure
"""Shared data models for the PubMed Stroke Monitor pipeline.

These dataclasses mirror the definitions in docs/definitions/.
"""

from dataclasses import dataclass, field


@dataclass
class PubmedRecord:
    """Core domain object flowing through the pipeline.

    See docs/definitions/pubmed-record.md for the canonical schema.
    """

    pmid: str
    title: str
    authors: list[str]
    journal: str
    abstract: str
    pub_date: str
    article_types: list[str]
    mesh_terms: list[str]
    language: str
    doi: str | None
    status: str  # "retrieved" | "filtered"
    triage_score: float | None = None
    triage_rationale: str | None = None


@dataclass
class LiteratureSummary:
    """Output of the summarization stage.

    See docs/definitions/literature-summary.md for the canonical schema.
    """

    pmid: str
    title: str
    journal: str
    pub_date: str
    subdomain: str
    citation: str
    research_question: str
    key_finding: str
    design: str
    primary_outcome: str
    limitations: str
    triage_score: float
    triage_rationale: str
    feedback_url: str
    raw_llm_response: str


@dataclass
class EmailDigest:
    """Assembled digest output.

    See docs/definitions/email-digest.md for the canonical schema.
    """

    date_range: str
    article_count: int
    title: str
    opening: str
    summaries: list[str]
    closing: str
    markdown: str
    plain_text: str


# --- Config models ---


@dataclass
class SearchConfig:
    """See docs/definitions/search-config.md."""

    mesh_terms: list[str]
    additional_terms: list[str] = field(default_factory=list)
    date_window_days: int = 7
    api_key: str | None = None
    retmax: int = 200
    require_abstract: bool = True
    rate_limit_delay: float = 0.4


@dataclass
class RuleFilterConfig:
    """See docs/definitions/filter-config.md (rule_filter section)."""

    include_article_types: list[str] = field(default_factory=list)
    exclude_article_types: list[str] = field(default_factory=list)
    exclude_mesh_terms: list[str] = field(default_factory=list)
    require_language: str = "eng"
    require_abstract: bool = True


@dataclass
class LLMTriageConfig:
    """See docs/definitions/filter-config.md (llm_triage section)."""

    model: str = "claude-sonnet-4-6"
    max_tokens: int = 150
    score_threshold: float = 0.70
    max_articles: int = 10
    use_prompt_caching: bool = True
    triage_prompt_file: str = "config/prompts/triage-prompt.md"


@dataclass
class FilterConfig:
    """See docs/definitions/filter-config.md."""

    rule_filter: RuleFilterConfig = field(default_factory=RuleFilterConfig)
    llm_triage: LLMTriageConfig = field(default_factory=LLMTriageConfig)
    priority_journals: list[str] = field(default_factory=list)


@dataclass
class SummaryConfig:
    """See docs/definitions/summary-config.md."""

    prompt_template: str = ""
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 500
    subdomain_options: list[str] = field(
        default_factory=lambda: [
            "Acute Treatment",
            "Prevention",
            "Rehabilitation",
            "Hospital Care",
            "Imaging",
            "Epidemiology",
        ]
    )
    feedback_form_url: str = ""
    feedback_pmid_field: str = ""


@dataclass
class OutputConfig:
    """See docs/definitions/distribute-config.md (output section)."""

    file: str = "output/digest.md"
    plain_text: bool = True
    plain_text_file: str = "output/digest.txt"


@dataclass
class DistributeConfig:
    """See docs/definitions/distribute-config.md."""

    digest_title: str = "Stroke Literature Weekly"
    opening: str = ""
    closing: str = ""
    sort_by: str = "triage_score"
    output: OutputConfig = field(default_factory=OutputConfig)
