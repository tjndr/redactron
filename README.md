# redactron

> Local-only CLI for batch PII redaction in PDFs.

**Status:** 🚧 Under active development — v1 target: 14 days

## What it does

redactron reads a profile YAML describing your PII (name aliases, addresses, phone numbers,
emails, account numbers, custom patterns), redacts all matching text from PDFs using
PyMuPDF, then verifies the redaction was complete. Everything runs on your machine — no
cloud calls, ever.

## Quickstart

```bash
pip install redactron          # once published to PyPI
redactron init                 # creates ~/.redactron/profile.yaml
# edit profile.yaml with your details
redactron run document.pdf     # redacts and verifies
```

## License

AGPL-3.0 — see [LICENSE](LICENSE).
 # tiny diff
