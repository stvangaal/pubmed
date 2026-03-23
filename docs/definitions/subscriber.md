# Subscriber

## Status
draft

## Version
v0

## Description
A digest recipient with optional topic preferences. Subscribers are configured in a YAML file and control which subdomains appear in their personalized email digest. An empty subdomains list means the subscriber receives all topics (opt-out model).

## Schema

```yaml
# config/subscribers.yaml

subscribers:
  - email: "user@example.com"
    name: "Alice"
    subdomains:           # empty list or omitted = all topics
      - "Acute Treatment"
      - "Prevention"

  - email: "bob@example.com"
    name: "Bob"
    subdomains: []        # receives everything
```

```python
@dataclass
class Subscriber:
    email: str                           # Recipient email address
    name: str = ""                       # Display name (optional)
    subdomains: list[str] = field(       # Topic preferences; empty = all
        default_factory=list
    )

@dataclass
class SubscriberDigest:
    subscriber: Subscriber               # The subscriber this digest is for
    digest: EmailDigest                  # Their personalized digest
```

## Constraints

- `email` must be a valid email address
- `subdomains` values must match entries in `summary-config.yaml`'s `subdomain_options`; unrecognized values are silently ignored (no articles will match)
- An empty `subdomains` list means the subscriber receives all topics
- When `config/subscribers.yaml` does not exist, the system falls back to `email-config.yaml`'s `to_addresses` with universal digests (all topics)

## Changelog

| Date | Version | Change | Affected Specs |
|------|---------|--------|----------------|
| 2026-03-23 | v0 | Initial draft | subscriber-preferences, digest-build, email-send |
