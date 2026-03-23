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

## Spec Index

| Spec | Phase | Status | Owns (files/directories) | Depends On |
|------|-------|--------|--------------------------|------------|
| pubmed-query | Phase 1 | ready | src/search/__init__.py, src/search/pubmed_query.py, src/search/date_normalize.py, tests/search/__init__.py, tests/search/test_pubmed_query.py, tests/search/test_date_normalize.py, config/search-config.yaml | search-config |
| rule-filter | Phase 1 | ready | src/filter/__init__.py, src/filter/rule_filter.py, tests/filter/__init__.py, tests/filter/test_rule_filter.py | pubmed-record, filter-config |
| llm-triage | Phase 1 | ready | src/filter/llm_triage.py, tests/filter/test_llm_triage.py, config/prompts/triage-prompt.md, config/filter-config.yaml | pubmed-record, filter-config |
| llm-summarize | Phase 2 | ready | src/summarize/__init__.py, src/summarize/llm_summarize.py, src/summarize/parse_summary.py, tests/summarize/__init__.py, tests/summarize/test_llm_summarize.py, tests/summarize/test_parse_summary.py, config/summary-config.yaml, config/prompts/summary-prompt.md | pubmed-record, summary-config |
| digest-build | Phase 2 | ready | src/distribute/__init__.py, src/distribute/digest_build.py, tests/distribute/__init__.py, tests/distribute/test_digest_build.py, config/distribute-config.yaml | literature-summary, distribute-config, blog-page |
| blog-publish | Phase 3 | ready | src/distribute/blog_publish.py, tests/distribute/test_blog_publish.py, config/blog-config.yaml, config/templates/blog-post.md, config/templates/blog-index.md | literature-summary, blog-config |
| email-send | Phase 3 | ready | src/distribute/email_send.py, tests/distribute/test_email_send.py, config/email-config.yaml | email-digest, email-config |
| project-infrastructure | Phase 0 | draft | src/__init__.py, tests/__init__.py, src/models.py, src/config.py, src/pipeline.py, requirements.txt, .gitignore | — |

## Phase Summary

| Phase | Specs (count) | Status |
|-------|--------------|--------|
| Phase 0 | 1 | draft |
| Phase 1 | 3 | ready |
| Phase 2 | 2 | ready |
| Phase 3 | 2 | ready |

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
