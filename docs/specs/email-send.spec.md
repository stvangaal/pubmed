---
name: email-send
status: ready
owner: distribute
owns:
  - src/distribute/email_send.py
  - tests/distribute/test_email_send.py
  - config/email-config.yaml
requires:
  - name: email-digest
    version: v0
  - name: email-config
    version: v0
provides: []
---

# Email Send

## Status
ready

## Target Phase
Phase 3

## Purpose
Send the assembled email digest to configured recipients via the Resend API. Converts the markdown digest to basic HTML for rich email clients and includes the plain-text version as a fallback. Runs as the final pipeline stage after blog-publish and digest-build.

## Requires (Inbound Contracts)

| Dependency | Source | Definition |
|------------|--------|------------|
| Assembled email digest | digest-build stage | `email-digest` v0 |
| Email configuration | user config | `email-config` v0 |

## Provides (Outbound Contracts)

None — terminal stage. The email is the final output.

## Behaviour

### Input
An `EmailDigest` object and an `EmailConfig`.

### Sending

1. **Check preconditions.** Skip sending (log and return false) if any of:
   - `config.enabled` is false
   - `config.to_addresses` is empty
   - `RESEND_API_KEY` environment variable is not set

2. **Render subject.** Substitute `{date_range}` and `{article_count}` placeholders in the subject template.

3. **Convert markdown to HTML.** Simple line-by-line conversion handling:
   - `**text**` → `<strong>`
   - `*text*` → `<em>`
   - `[text](url)` → `<a href>`
   - `- item` → `<ul><li>`
   - `---` → `<hr>`
   - Other lines → `<p>`
   - Empty lines are skipped (spacing comes from `<p>` and `<hr>` tags)

4. **Send via Resend API.** POST with `from`, `to`, `subject`, `html`, and `text` (plain-text fallback). Return true on success, false on failure.

### Error Handling
- If the API call fails, log a warning and return false — do not halt the pipeline. The digest files are already written; email is best-effort.

## Decisions

| ID | Decision | Alternatives Considered | Rationale | Date |
|----|----------|------------------------|-----------|------|
| ES1 | Resend for email delivery | SendGrid; AWS SES; SMTP | Simplest API, generous free tier (100/day), single sender email verification (no DNS needed to start). | 2026-03-23 |
| ES2 | Simple markdown-to-HTML converter, no external library | markdown2; mistune; send markdown as-is | Avoids a dependency for a straightforward conversion. The digest format is predictable — only bold, italic, links, lists, and rules. Plain-text fallback covers clients that strip HTML. | 2026-03-23 |
| ES3 | Email send is best-effort, never halts pipeline | Halt on failure; retry | The digest files and blog page are already produced. Email failure is recoverable — the comms person can still paste from the output files. | 2026-03-23 |

## Tests

### Unit Tests

- **test_markdown_to_html_bold**: Verify `**text**` converts to `<strong>text</strong>`.
- **test_markdown_to_html_links**: Verify `[text](url)` converts to `<a href="url">text</a>`.
- **test_markdown_to_html_list**: Verify bullet items produce `<ul><li>` structure.
- **test_markdown_to_html_hr**: Verify `---` produces `<hr>`.
- **test_markdown_to_html_no_extra_breaks**: Verify empty lines don't produce `<br>` tags.
- **test_subject_template**: Verify `{date_range}` and `{article_count}` are substituted in subject.
- **test_skip_when_disabled**: When `enabled: false`, verify no API call is made.
- **test_skip_when_no_key**: When `RESEND_API_KEY` is unset, verify no API call is made.
- **test_skip_when_no_recipients**: When `to_addresses` is empty, verify no API call is made.

### Contract Tests

- **test_config_matches_email_config_schema**: Verify `config/email-config.yaml` deserializes into a valid `EmailConfig`.

### Integration Tests

- **test_send_real_email**: Send a test email via the Resend API and verify a success response. (Requires `RESEND_API_KEY`; skip in CI if not available.)

## Implementation Notes

- `RESEND_API_KEY` is read from the environment (same pattern as `ANTHROPIC_API_KEY`).
- The `onboarding@resend.dev` test sender only delivers to the Resend account owner's email. For sending to other recipients, a custom domain must be verified in Resend.
