---
name: rule-filter
status: ready
owner: filter
owns:
  - src/filter/rule_filter.py
  - tests/filter/test_rule_filter.py
requires:
  - name: pubmed-record
    version: v0
  - name: filter-config
    version: v0
provides:
  - name: pubmed-record
    version: v0
---

# Rule Filter

## Status
ready

## Target Phase
Phase 1

## Purpose
Apply deterministic, cost-free filtering to the raw PubMed search results. Removes obviously irrelevant articles (animal studies, non-English, case reports, no abstract) before the LLM triage stage spends tokens on them. This is the first pass of the two-pass hybrid filter.

## Requires (Inbound Contracts)

| Dependency | Source | Definition |
|------------|--------|------------|
| Retrieved PubMed records | search stage | `pubmed-record` v0 (`@retrieved` status) |
| Filter configuration | user config | `filter-config` v0 (`rule_filter` section) |

## Provides (Outbound Contracts)

| Export | Type | Definition |
|--------|------|------------|
| Rule-filtered records | data | `pubmed-record` v0 (still `@retrieved` status — triage fields remain `None`) |
| Exclusion log | data | inline — list of excluded records with reasons |

## Behaviour

### Input
A list of `PubmedRecord` objects with status `@retrieved` and a `RuleFilterConfig`. The input may include both MeSH-indexed and preindex articles (distinguished by the `preindex` flag). All articles are filtered identically — the `preindex` and `source_topic` fields are preserved unchanged through filtering.

### Processing
For each record, apply filters in this order (short-circuit on first exclusion):

1. **Abstract check** — if `require_abstract` is true and `abstract` is empty, exclude with reason `"no abstract"`.
2. **Language check** — if `language` does not match `require_language`, exclude with reason `"language: {actual}"`.
3. **Animal study check** — if any MeSH term (case-insensitive) matches `exclude_mesh_terms` AND "humans" is NOT in the MeSH terms, exclude with reason `"animal study"`.
4. **Article type check** — if any article type matches `exclude_article_types` AND no article type matches `include_article_types`, exclude with reason `"excluded type: {matched types}"`. Include types take precedence over exclude types (e.g., a "Randomized Controlled Trial" that is also a "Case Reports" passes).

### Output

Two lists:
- **passed** — `PubmedRecord` objects that survived all rules (status remains `@retrieved`, triage fields remain `None`)
- **excluded** — list of `(PubmedRecord, reason: str)` tuples, one per excluded article

The exclusion log is written to the pipeline's output directory as `filter-exclusions.json` for troubleshooting. Each entry includes the PMID, title, journal, and exclusion reason.

## Decisions

| ID | Decision | Alternatives Considered | Rationale | Date |
|----|----------|------------------------|-----------|------|
| RF1 | Include types take precedence over exclude types | Exclude takes precedence; strict exclusion | An article tagged as both "Randomized Controlled Trial" and "Case Reports" is more likely a trial worth reviewing. Inclusive policy avoids false negatives. | 2026-03-23 |
| RF2 | Animal study check uses MeSH terms, not article types | Check title keywords; check abstract | MeSH "Animals" is the authoritative signal. Title/abstract keyword matching would produce false positives (e.g., "animal models" mentioned in discussion of a human study). | 2026-03-23 |
| RF3 | Write exclusion log to file | Log only; discard | Persistent exclusion log enables troubleshooting false negatives (e.g., the AF guideline that was initially missed). No cost to storing it. | 2026-03-23 |

## Tests

### Unit Tests

- **test_exclude_no_abstract**: Record with empty abstract is excluded with reason "no abstract".
- **test_exclude_non_english**: Record with `language="chi"` is excluded.
- **test_exclude_animal_study**: Record with MeSH "Animals", "Mice" and no "Humans" is excluded.
- **test_pass_human_and_animal_mesh**: Record with both "Humans" and "Animals" in MeSH passes (human study that references animal data).
- **test_exclude_case_report**: Record with article type "Case Reports" and no include types is excluded.
- **test_include_overrides_exclude**: Record with both "Randomized Controlled Trial" and "Case Reports" passes.
- **test_all_filters_pass**: Record that passes all criteria is included in output.
- **test_exclusion_log_format**: Verify exclusion log entries include PMID, title, journal, and reason.

### Contract Tests

- **test_output_preserves_pubmed_record_schema**: Verify output records conform to `pubmed-record` v0 with status still `"retrieved"` and triage fields `None`.
- **test_config_matches_filter_config_schema**: Verify `config/filter-config.yaml` `rule_filter` section deserializes correctly.

### Integration Tests

N/A — no cross-spec dependencies. Rule filter is a pure function of its inputs.

## Implementation Notes

- All string comparisons for article types, MeSH terms, and language should be case-insensitive.
- The exclusion log should be machine-readable (JSON) for potential future use in feedback loops.
- Filter order matters for performance but not correctness — the cheapest checks (abstract, language) come first.
