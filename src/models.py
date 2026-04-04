# owner: project-infrastructure
"""Shared data models for the PubMed Stroke Monitor pipeline.

These dataclasses mirror the definitions in docs/definitions/.
"""

from dataclasses import dataclass, field


@dataclass
class LLMUsage:
    """Token usage and estimated cost for a pipeline stage."""

    stage: str
    model: str
    call_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    # Anthropic pricing per million tokens (Claude Sonnet 4.6 defaults)
    _INPUT_COST_PER_M: float = 3.00
    _OUTPUT_COST_PER_M: float = 15.00
    _CACHE_WRITE_COST_PER_M: float = 3.75
    _CACHE_READ_COST_PER_M: float = 0.30

    @property
    def estimated_cost(self) -> float:
        """Estimated cost in USD based on Anthropic Sonnet 4.6 pricing."""
        return (
            self.input_tokens * self._INPUT_COST_PER_M
            + self.output_tokens * self._OUTPUT_COST_PER_M
            + self.cache_creation_input_tokens * self._CACHE_WRITE_COST_PER_M
            + self.cache_read_input_tokens * self._CACHE_READ_COST_PER_M
        ) / 1_000_000

    def add_response(self, usage) -> None:
        """Accumulate token counts from an Anthropic API response.usage object."""
        self.call_count += 1
        self.input_tokens += getattr(usage, "input_tokens", 0)
        self.output_tokens += getattr(usage, "output_tokens", 0)
        self.cache_creation_input_tokens += getattr(
            usage, "cache_creation_input_tokens", 0
        ) or 0
        self.cache_read_input_tokens += getattr(
            usage, "cache_read_input_tokens", 0
        ) or 0


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
    source_topic: str = ""
    preindex: bool = False
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
    tags: list[str]
    citation: str
    research_question: str
    key_finding: str
    design: str
    primary_outcome: str
    limitations: str
    summary_short: str
    triage_score: float
    triage_rationale: str
    feedback_url: str
    raw_llm_response: str
    source_topic: str = ""
    preindex: bool = False
    article_types: list[str] = field(default_factory=list)

    @property
    def subdomain(self) -> str:
        """Primary tag (first in list). Backward-compat with single-tag code paths."""
        return self.tags[0] if self.tags else "General"


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
    llm_usage: list["LLMUsage"] = field(default_factory=list)


# --- Config models ---


@dataclass
class Topic:
    """A named search topic within a program.

    Each topic runs as an independent PubMed query.  It inherits
    date_window_days, retmax, require_abstract, rate_limit_delay, and
    api_key from the parent SearchConfig.

    Topics are co-equal within a program — there is no distinguished
    "main" topic.  For backward compatibility, a top-level mesh_terms
    in SearchConfig still works as an implicit primary search.
    """

    name: str
    mesh_terms: list[str]
    additional_terms: list[str] = field(default_factory=list)
    triage_prompt_file: str | None = None


# Backward-compat alias
SearchProfile = Topic


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
    topics: list[Topic] = field(default_factory=list)


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
    min_articles: int = 0
    min_score_floor: float = 0.50
    use_prompt_caching: bool = True
    triage_prompt_file: str = "config/prompts/triage-prompt.md"
    seen_pmids_file: str = "data/seen-pmids.json"


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
    max_tokens: int = 600
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
    full_summary_threshold: float = 0.80
    output: OutputConfig = field(default_factory=OutputConfig)


@dataclass
class BlogTemplatesConfig:
    """See docs/definitions/blog-config.md (templates section)."""

    post: str = "config/templates/blog-post.md"
    index: str = "config/templates/blog-index.md"


@dataclass
class BlogConfig:
    """See docs/definitions/blog-config.md."""

    site_title: str = "Stroke Literature Weekly"
    site_description: str = ""
    base_url: str = ""
    publish: bool = True
    branch: str = "gh-pages"
    digests_dir: str = "digests"
    closing: str = ""
    templates: BlogTemplatesConfig = field(default_factory=BlogTemplatesConfig)


@dataclass
class EmailConfig:
    """See docs/definitions/email-config.md."""

    enabled: bool = True
    from_address: str = "onboarding@resend.dev"
    to_addresses: list[str] = field(default_factory=list)
    subject: str = "Stroke Literature Weekly — {date_range}"
    owner_email: str | None = None


@dataclass
class WordPressConfig:
    """See docs/definitions/wp-config.md."""

    enabled: bool = False
    site_url: str = ""
    clinical_topics_taxonomy: str = "clinical_topics"
    pages: list[str] = field(default_factory=list)


@dataclass
class BlogPage:
    """See docs/definitions/blog-page.md."""

    run_date: str
    page_url: str
    article_urls: dict[str, str]  # PMID → anchor URL
    markdown: str
    published: bool
