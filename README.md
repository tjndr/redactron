# Redactron — Local-only PII redaction for PDFs

> Your files stay on your machine. No cloud. No subscription. No telemetry.

[![PyPI](https://img.shields.io/pypi/v/redactron)](https://pypi.org/project/redactron/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)

Redactron is an on-device privacy tool for redacting PII from PDFs. Define your PII once in a profile, run it against any number of documents, and get a verified redacted output — all without a single byte leaving your machine.

Encrypted multi-client vault. Touch ID gated on macOS. Audit log. OCR fallback for scanned documents. AGPL-3.0.

---

<!-- Demo GIF placeholder — add after first public release -->

---

## Why Redactron?

**Your files stay local.** Every cloud redaction service — Adobe, iLovePDF, SmallPDF — uploads your documents to their servers. Redactron runs entirely on your machine. The PDF never leaves.

**No subscription.** No per-page fees. No upsells. Install once, use forever.

**Zero-trust, auditable source.** AGPL-3.0 means the full source is available for inspection. No black-box ML model deciding what to redact. You define exactly what gets removed.

**Professional-grade.** AES-256-GCM encrypted vault for multiple client profiles. Touch ID gate on macOS (via LocalAuthentication). SQLite audit log of every run. Post-redaction verification that re-scans the output and reports survivors.

## Comparison

| | Redactron | Adobe Acrobat | iLovePDF | SmallPDF |
|---|:---:|:---:|:---:|:---:|
| Files leave your machine? | ❌ Never | ✅ Cloud | ✅ Cloud | ✅ Cloud |
| Subscription required? | ❌ Free | ✅ $20+/mo | ✅ Freemium | ✅ Freemium |
| Ads / upsells? | ❌ None | ✅ Yes | ✅ Yes | ✅ Yes |
| Audit log? | ✅ SQLite | ❌ No | ❌ No | ❌ No |
| Multi-client support? | ✅ Encrypted vault | ❌ No | ❌ No | ❌ No |
| Verification report? | ✅ Built-in | ❌ No | ❌ No | ❌ No |
| Source available? | ✅ AGPL-3.0 | ❌ Proprietary | ❌ Proprietary | ❌ Proprietary |
| Works offline? | ✅ Always | ⚠️ Partial | ❌ No | ❌ No |

*Comparison reflects publicly available information as of May 2026. Cloud services may change their terms.*

## Quickstart

```bash
pip install redactron
redactron init
redactron vault init
redactron profile add --client me --from docs/examples/profile-template.yaml
redactron run document.pdf --client me
```

That's it. `document_redacted.pdf` is in the same directory, alongside a verification report.

## Features

- **Profile-driven** — define your PII once (names, aliases, addresses, phones, emails, SSNs, account numbers, custom regex); redact any number of PDFs
- **Encrypted vault** — AES-256-GCM encrypted multi-client profile store; master key in macOS Keychain
- **Touch ID gate** — LocalAuthentication soft-gate before every vault access on macOS
- **OCR fallback** — auto-triggers on image-only pages via pytesseract; no flag needed
- **Layout-aware** — column-aware address bridging prevents cross-column false positives in two-column PDFs
- **Verification** — re-scans the redacted output and reports any PII survivors
- **Audit log** — SQLite record of every run (filename, detections, verification status)
- **Batch mode** — `redactron run ./docs/` redacts an entire directory; outputs go to `redacted/` subdir
- **Consolidated report** — single `YYYY-MM-DD-HHMM_batch-summary.md` per batch run
- **Dry run** — preview detections without writing output

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

Copy `docs/examples/profile-template.yaml` for the full annotated schema.

## Multi-client vault

```bash
redactron vault init
redactron profile add --client alice --from alice.yaml
redactron profile add --client bob --from bob.yaml
redactron run statement.pdf --client alice
redactron profile list
```

## Security model

The vault is AES-256-GCM encrypted at rest. On macOS, the master key is stored in the login keychain and access is gated by a Touch ID prompt via LocalAuthentication.

**Touch ID is soft enforcement** — it gates redactron's code path, not the keychain item itself. An unsigned Python package cannot use `kSecAttrAccessControl` (requires Apple code-signing entitlements). See [docs/SECURITY.md](docs/SECURITY.md) for the full threat model.

## Performance targets

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
redactron run <path> [--client <id>] [--no-ocr] [--force-ocr] [--no-verify]
                     [--json] [--output <path>] [--quiet] [--per-file-reports]
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
redactron --version
```

## Documentation

- [docs/PROFILE.md](docs/PROFILE.md) — full profile schema reference
- [docs/SECURITY.md](docs/SECURITY.md) — threat model, crypto choices, Touch ID implementation
- [docs/PRIVACY.md](docs/PRIVACY.md) — local-only guarantee, audit DB schema, AGPL licensing
- [docs/RELEASING.md](docs/RELEASING.md) — how to cut a release
- [CONTRIBUTING.md](CONTRIBUTING.md) — dev setup, conventions, PR process
- [CHANGELOG.md](CHANGELOG.md) — version history

## License

AGPL-3.0 — see [LICENSE](LICENSE).

Redactron depends on [PyMuPDF](https://pymupdf.readthedocs.io/) which is also AGPL-3.0. If you distribute redactron as part of a proprietary product, the AGPL requires you to release your source. See [docs/PRIVACY.md](docs/PRIVACY.md) for details.
