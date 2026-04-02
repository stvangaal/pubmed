# Email Config

## Status
draft

## Version
v0

## Description
User-facing configuration for email delivery. Controls the sender address, recipient list, subject line template, and whether sending is enabled. Users edit this as a YAML file without touching source code.

## Schema

```yaml
# config/email-config.yaml

# Whether to actually send emails (set false for local dev / dry runs)
enabled: true

# Sender address (must be verified in Resend, or use onboarding@resend.dev for testing)
from_address: "onboarding@resend.dev"

# Recipient list
to_addresses:
  - "recipient@example.com"

# Email subject line — supports {date_range} and {article_count} placeholders
subject: "Stroke Literature Weekly — {date_range}"
```

```python
@dataclass
class EmailConfig:
    enabled: bool              # Whether to send emails
    from_address: str          # Verified sender address
    to_addresses: list[str]    # Recipient email addresses
    subject: str               # Subject template with {date_range}, {article_count} placeholders
    owner_email: str | None    # Domain owner email for troubleshooting reports
```

## Domain Scoping

When `--domain` is specified, this config is loaded from `config/domains/{domain}/email-config.yaml` instead of `config/email-config.yaml`. The schema is identical in both layouts. Each domain has its own sender, recipients, and subject template. See architecture decision A10.

## Constraints

- `from_address` must be a verified sender in Resend (or `onboarding@resend.dev` for testing)
- `to_addresses` must contain at least one valid email when `enabled` is true
- `subject` may contain `{date_range}` and `{article_count}` placeholders — both are optional
- When using `onboarding@resend.dev`, emails can only be delivered to the Resend account owner's email

## Changelog

| Date | Version | Change | Affected Specs |
|------|---------|--------|----------------|
| 2026-03-23 | v0 | Initial draft | — |
