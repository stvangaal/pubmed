# Project Register

## Definitions Index

| Definition | Version | Status | Primary Implementor | Required By |
|------------|---------|--------|---------------------|-------------|
| pubmed-record | v0 | draft | — | pubmed-query, rule-filter, llm-triage, llm-summarize |
| search-config | v0 | draft | — | pubmed-query |
| filter-config | v0 | draft | — | rule-filter, llm-triage |
| summary-config | v0 | draft | — | llm-summarize |
| blog-config | v0 | draft | — | blog-publish |
| distribute-config | v0 | draft | — | digest-build |
| literature-summary | v0 | draft | — | llm-summarize, blog-publish, digest-build |
| blog-page | v0 | draft | — | blog-publish |
| email-config | v0 | draft | — | email-send |
| email-digest | v0 | draft | — | digest-build, email-send |
| wp-config | v0 | draft | — | wp-publish |

## Spec Index

| Spec | Phase | Status | Owns (files/directories) | Depends On |
|------|-------|--------|--------------------------|------------|
| pubmed-query | Phase 1 | ready | src/search/__init__.py, src/search/pubmed_query.py, src/search/date_normalize.py, tests/search/__init__.py, tests/search/test_pubmed_query.py, tests/search/test_date_normalize.py, tests/search/test_multi_search.py, config/search-config.yaml | search-config, filter-config (priority_journals for preindex) |
| rule-filter | Phase 1 | ready | src/filter/__init__.py, src/filter/rule_filter.py, tests/filter/__init__.py, tests/filter/test_rule_filter.py | pubmed-record, filter-config |
| llm-triage | Phase 1 | ready | src/filter/llm_triage.py, tests/filter/test_llm_triage.py, config/prompts/triage-prompt.md, config/filter-config.yaml | pubmed-record, filter-config |
| llm-summarize | Phase 2 | ready | src/summarize/__init__.py, src/summarize/llm_summarize.py, src/summarize/parse_summary.py, tests/summarize/__init__.py, tests/summarize/test_llm_summarize.py, tests/summarize/test_parse_summary.py, config/summary-config.yaml, config/prompts/summary-prompt.md | pubmed-record, summary-config |
| digest-build | Phase 2 | in-progress | src/distribute/__init__.py, src/distribute/digest_build.py, tests/distribute/__init__.py, tests/distribute/test_digest_build.py, config/distribute-config.yaml | literature-summary, distribute-config, blog-page |
| blog-publish | Phase 3 | ready | src/distribute/blog_publish.py, tests/distribute/test_blog_publish.py, config/blog-config.yaml, config/templates/blog-post.md, config/templates/blog-index.md | literature-summary, blog-config |
| email-send | Phase 3 | in-progress | src/distribute/email_send.py, tests/distribute/test_email_send.py | email-digest, email-config |
| wp-publish | Phase 3 | in-progress | src/distribute/wp_publish.py, src/distribute/wp_members.py, src/distribute/wp_digest.py, tests/distribute/test_wp_publish.py, tests/distribute/test_wp_members.py, wordpress/pubmed-pipeline.php, docs/wordpress-setup.md, config/domains/_template/wp-config.yaml, config/domains/stroke/wp-config.yaml, config/domains/neurology/wp-config.yaml, .github/workflows/weekly-member-digest.yml | literature-summary, wp-config |
| wp-pages | Phase 3 | in-progress | src/distribute/wp_pages.py, tests/distribute/test_wp_pages.py, content/pages/_defaults/privacy-policy.md, content/pages/_defaults/terms-of-use.md, content/pages/_defaults/disclaimer.md, content/pages/_defaults/about.md, content/pages/_defaults/landing.md, .github/workflows/sync-wp-pages-stroke.yml, .github/workflows/sync-wp-pages-neurology.yml | wp-config |
| project-infrastructure | Phase 0 | draft | src/__init__.py, tests/__init__.py, src/models.py, src/config.py, src/pipeline.py, requirements.txt, .gitignore | — |
| domain-config | Phase 4 | implemented | config/domains/_template/domain.yaml, config/domains/_template/search-config.yaml, config/domains/_template/filter-config.yaml, config/domains/_template/summary-config.yaml, config/domains/_template/distribute-config.yaml, config/domains/_template/blog-config.yaml, config/domains/_template/email-config.yaml, config/domains/_template/prompts/triage-prompt.md, config/domains/_template/prompts/summary-prompt.md, config/domains/CHANGELOG.md, tests/test_domain_config.py | — |
| stroke-migration | Phase 4 | implemented | config/domains/stroke/domain.yaml, config/domains/stroke/search-config.yaml, config/domains/stroke/filter-config.yaml, config/domains/stroke/summary-config.yaml, config/domains/stroke/distribute-config.yaml, config/domains/stroke/blog-config.yaml, config/domains/stroke/email-config.yaml, config/domains/stroke/prompts/triage-prompt.md, config/domains/stroke/prompts/summary-prompt.md | domain-config |
| neurology-setup | Phase 4 | draft | config/domains/neurology/domain.yaml, config/domains/neurology/search-config.yaml, config/domains/neurology/filter-config.yaml, config/domains/neurology/summary-config.yaml, config/domains/neurology/distribute-config.yaml, config/domains/neurology/blog-config.yaml, config/domains/neurology/email-config.yaml, config/domains/neurology/prompts/triage-prompt.md, config/domains/neurology/prompts/summary-prompt.md | domain-config |

## Phase Summary

| Status | Count |
|--------|-------|
| draft | 1 |
| ready | 5 |
| in-progress | 3 |
| implemented | 2 |

## Unowned Code
<!-- This section should always be empty. If it is not, something
     needs to be assigned to a spec or deleted. -->

## Dependency Resolution Order
<!-- Topological sort of the spec dependency graph, grouped by phase.
     This is the order in which specs should be implemented. -->

### Phase 0
1. project-infrastructure (no dependencies)

### Phase 1
2. pubmed-query (no cross-spec dependencies)
3. rule-filter (needs pubmed-record from search stage)
4. llm-triage (needs rule-filter output)

### Phase 2
5. llm-summarize (needs pubmed-record@filtered)
6. digest-build (needs literature-summary@summarized)

### Phase 3
7. blog-publish (needs literature-summary@summarized; digest-build updated to accept blog URLs)
8. email-send (needs email-digest@assembled)

### Phase 4
9. domain-config (depends on project-infrastructure for config.py and pipeline.py)
10. stroke-migration [disposable] (depends on domain-config for the target layout)
11. neurology-setup (depends on domain-config for the target layout)
