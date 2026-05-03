# redactron

> Local-only CLI for batch PII redaction in PDFs. No cloud. No telemetry. Verified output.

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)

## What it does

redactron reads a profile YAML describing your PII — name aliases, addresses, phone numbers,
emails, account numbers, custom regex patterns — redacts all matching text from PDFs using
PyMuPDF, then verifies the redaction was complete. Everything runs on your machine. No data
ever leaves your device.

## Quickstart

```bash
pip install redactron
redactron init                 # creates ~/.redactron/profile.yaml
# edit ~/.redactron/profile.yaml with your details
redactron run document.pdf     # redacts → document_redacted.pdf + verification report
```

## Features

- **Profile-driven** — define your PII once in a YAML file; redact any number of PDFs
- **Multi-detector** — name fuzzy-match, address parsing, account numbers, custom regex, Presidio NLP
- **OCR fallback** — `--ocr` flag handles scanned/image-only PDFs via pytesseract
- **Verification** — re-scans the redacted output and reports any survivors
- **Multi-client vault** — AES-256-GCM encrypted vault for multiple client profiles
- **Audit log** — SQLite log of every redaction run
- **Batch mode** — `redactron run ./docs/` redacts an entire directory
- **Dry run** — `redactron dry-run doc.pdf` previews detections without writing output

## Profile example

```yaml
version: 1
subject:
  display_name: "Jane Smith"
  aliases: ["Jane", "J. Smith"]
  addresses: ["123 Main Street, Springfield, IL 62701"]
  phones: ["+1-555-867-5309"]
  emails: ["jane@example.com"]
  account_numbers:
    - value: "ACC-9900112233"
      preserve_last: 4
detection:
  fuzzy_match: true
  match_threshold: 0.85
```

See [docs/PROFILE.md](docs/PROFILE.md) for the full schema reference.

## Multi-client vault

```bash
redactron vault init
redactron profile add --client alice --name "Alice Smith"
redactron profile add --client bob --from bob_profile.yaml
redactron run statement.pdf --client alice
redactron profile list
```

The vault is AES-256-GCM encrypted at rest. On macOS, the master key is stored in the
login keychain and access is gated by a Touch ID prompt via LocalAuthentication.

**Security model:** Touch ID is soft enforcement — it gates redactron's code path, not the
keychain item itself. An unsigned Python package cannot use `kSecAttrAccessControl`
(requires Apple code-signing entitlements). See [docs/SECURITY.md](docs/SECURITY.md) for
the full threat model.

## Performance targets (v1)

| Scenario | Target |
|---|---|
| 10-page text PDF | < 3 seconds end-to-end |
| 10-page image PDF (OCR) | < 30 seconds |
| Peak memory per document | < 500 MB |

## Platform support

| Platform | Status |
|---|---|
| macOS | ✅ First-class (Touch ID vault) |
| Linux | 🔜 v1.1 (keyring via libsecret) |
| Windows | 🔜 v1.1 (DPAPI) |

## CLI reference

```
redactron run <path> [--ocr] [--client <id>] [--no-verify] [--json] [--output <path>]
redactron dry-run <path> [--json]
redactron verify <path>
redactron init
redactron vault init
redactron profile add --client <id> [--name <name>] [--from <yaml>]
redactron profile list
redactron profile show <id> [--reveal]
redactron profile edit <id>
redactron profile delete <id>
redactron profile import <yaml> [--client <id>]
redactron log [--subject <id>] [--limit N]
redactron report <run-id>
```

## License

AGPL-3.0 — see [LICENSE](LICENSE).

redactron depends on [PyMuPDF](https://pymupdf.readthedocs.io/) which is also AGPL-3.0.
If you distribute redactron as part of a proprietary product, the AGPL requires you to
release your source. See [docs/PRIVACY.md](docs/PRIVACY.md) for details.
