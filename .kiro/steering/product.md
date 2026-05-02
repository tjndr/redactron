# Product

## What
redactron is a local-only CLI that batch-redacts PII from PDFs using a user-defined
profile, then verifies the redaction was complete. All processing happens on the
user's machine.

## Target users
1. Privacy-minded individuals (financial/medical PDFs)
2. Solo professionals (lawyers, doctors, accountants, journalists)
3. Small clinics/firms needing simple HIPAA/GLBA-aware workflows

## Non-goals (v1)
- Cloud SaaS
- Multi-user web app
- Real-time/streaming redaction
- Editing redacted output (it is permanent by design)
- Tax/legal advice

## Differentiator
Local-only + profile-driven + verification report. No equivalent OSS tool exists.

## License
AGPL-3.0 (PyMuPDF compatibility).