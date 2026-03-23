---
name: subscriber-preferences
status: draft
owner: distribute
owns:
  - config/subscribers.yaml
requires:
  - name: subscriber
    version: v0
  - name: literature-summary
    version: v0
  - name: distribute-config
    version: v0
provides:
  - name: subscriber
    version: v0
---

# Subscriber Preferences

## Status
draft

## Target Phase
Phase 3

## Purpose
Allow individual subscribers to choose which subdomains they receive in their email digest. Each subscriber's preferences are stored in `config/subscribers.yaml` and applied during digest construction to filter articles by subdomain. The blog and universal digest files remain unaffected — personalization only applies to email delivery.

## Requires (Inbound Contracts)

| Dependency | Source | Definition |
|------------|--------|------------|
| Literature summaries | summarize stage | `literature-summary` v0 |
| Distribution configuration | user config | `distribute-config` v0 |
| Subscriber profiles | user config | `subscriber` v0 |

## Provides (Outbound Contracts)

| Export | Type | Definition |
|--------|------|------------|
| Subscriber profiles | config | `subscriber` v0 |

## Behaviour

### Configuration

Subscribers are defined in `config/subscribers.yaml`. Each entry has:
- `email` (required): recipient address
- `name` (optional): display name for logging
- `subdomains` (optional): list of subdomain strings to include; empty or omitted means all topics

### Fallback

When `config/subscribers.yaml` does not exist, the system falls back to `email-config.yaml`'s `to_addresses`, treating each address as a subscriber with no subdomain preferences (universal digest).

### Filtering

For each subscriber:
1. If `subdomains` is empty → include all summaries
2. If `subdomains` is non-empty → include only summaries whose `subdomain` field matches one of the subscriber's preferred subdomains

### Integration Points

- **`config.py` → `load_subscribers()`**: Loads subscriber profiles; falls back to `email-config.to_addresses`
- **`digest_build.py` → `build_subscriber_digests()`**: Filters summaries per subscriber, calls `_assemble_digest()` for each
- **`email_send.py` → `send_subscriber_digests()`**: Sends one personalized email per subscriber
- **`pipeline.py`**: Loads subscribers, builds per-subscriber digests, sends individually

### Unchanged Behaviour

- Blog publishing remains universal (all articles)
- Universal digest files (`output/digest.md`, `output/digest.txt`) still contain all articles
- `send_digest()` remains as fallback when no subscribers are configured

## Decisions

| ID | Decision | Alternatives Considered | Rationale | Date |
|----|----------|------------------------|-----------|------|
| SP1 | Opt-out model (empty = all topics) | Opt-in (empty = nothing) | Safer default — new subscribers get everything without requiring configuration. Matches current single-recipient behaviour. | 2026-03-23 |
| SP2 | Separate subscribers.yaml file | Extend email-config.yaml | Keeps subscriber concerns separate from send-level config. Avoids email-config growing into a god-config. | 2026-03-23 |
| SP3 | Filter at digest-build, not earlier | Filter at search/triage stage | All articles should still be triaged and summarized — personalization is a presentation concern, not a relevance concern. Blog and universal digest need all articles. | 2026-03-23 |
| SP4 | One Resend API call per subscriber | Single API call with BCC | Each subscriber gets different content — BCC is not possible with personalized digests. | 2026-03-23 |

## Tests

### Unit Tests

- **test_load_subscribers_from_yaml**: Verify subscribers are loaded from YAML with correct fields.
- **test_load_subscribers_fallback**: When no subscribers.yaml exists, verify fallback to email-config to_addresses.
- **test_load_subscribers_empty_subdomains**: Verify empty subdomains list is preserved (not converted to None).
- **test_filter_by_subdomain**: Given a subscriber with ["Acute Treatment"], verify only matching summaries are included.
- **test_no_filter_empty_subdomains**: Given a subscriber with empty subdomains, verify all summaries are included.
- **test_no_matching_articles**: Given a subscriber whose subdomains match nothing, verify empty-week digest is produced.
- **test_multiple_subscribers_different_preferences**: Verify each subscriber gets a different digest based on their preferences.
- **test_send_subscriber_digests_calls_per_subscriber**: Verify one API call is made per subscriber.

### Contract Tests

- **test_config_matches_subscriber_schema**: Verify `config/subscribers.yaml` deserializes into valid `Subscriber` objects.
- **test_subdomain_values_valid**: Verify configured subdomains match `summary-config.yaml`'s `subdomain_options`.

## Implementation Notes

- The `_assemble_digest()` function (extracted from `build_digest()`) is the core reusable unit — it takes a filtered summary list and produces an `EmailDigest` with no side effects.
- `build_subscriber_digests()` calls `_assemble_digest()` once per subscriber — this is efficient for the expected scale (under 50 subscribers).
- The universal `build_digest()` function is unchanged and continues to write output files and print to stdout.
