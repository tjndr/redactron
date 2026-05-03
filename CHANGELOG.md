# Changelog

All notable changes to redactron are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] — 2026-05-03

First public release. Covers milestones M1–M4 and M3.5.

### Added

**M1 — Core engine**
- PyMuPDF text extraction with character-level bounding boxes (`extract/text_layer.py`)
- Name fuzzy-match detector via rapidfuzz (`detect/name_detector.py`)
- Address detector via usaddress with multi-line bridge (`detect/address_detector.py`)
- Account number / custom regex detector (`detect/account_detector.py`)
- Presidio NLP detector with configurable entities (`detect/presidio_detector.py`)
- Redaction engine with bbox sanity guards — rejects rects >30% page area or >4× median line height (`redact/engine.py`)
- Partial-match account number redaction with `preserve_last` (`redact/partial.py`)
- Post-redaction verification — re-scans output and reports survivors (`verify/verifier.py`)
- Safety-net multi-pass pipeline — up to 3 passes until no survivors (`pipeline.py`)

**M2 — Profile + variants**
- Pydantic v2 profile schema with full validation (`profile.py`)
- `redactron init` — creates default `~/.redactron/profile.yaml`
- `redactron run` — redacts a file or directory with progress bar
- `redactron dry-run` — previews detections without writing output
- `redactron verify` — standalone verification of a redacted PDF
- Batch mode — `redactron run ./docs/` redacts entire directories
- JSON output mode (`--json`) for scripting
- Audit log — SQLite record of every run (`audit/log.py`)
- Markdown report generation (`report/markdown.py`)

**M3 — Verification + audit**
- `redactron log` — view audit history
- `redactron report <id>` — re-render report from audit log
- `redactron subject add/list/show` — subject management

**M3.5 — Encrypted multi-client vault**
- AES-256-GCM encrypted vault (`vault/store.py`, `vault/keychain.py`)
- macOS Keychain integration with Touch ID via LocalAuthentication (`vault/keychain_macos.py`)
- `redactron vault init` — creates encrypted vault
- `redactron profile add/list/show/edit/delete/rename/import` — full profile CRUD
- `redactron run --client <id>` — load profile from vault
- Migration from legacy `profile.yaml` with secure-wipe (`vault/migrate.py`)

**M4 — Polish + launch**
- OCR fallback for image-only PDFs via pytesseract (`extract/ocr.py`)
  - Per-page auto-trigger, 300 DPI render, 72/dpi coordinate conversion
  - Confidence threshold 60, bbox sanity guards
  - Image-region painting (draw_rect) for OCR redactions
- `--ocr` / `--no-ocr` CLI flag on `redactron run`
- Synthetic test corpus — 12 document types, 3 E2E assertions each (`tests/test_corpus.py`)
- Full documentation: README, PROFILE.md, PRIVACY.md, SECURITY.md, CHANGELOG.md, CONTRIBUTING.md
- PyPI release infrastructure (release.yml, trusted publishing)

### Dependencies

- pymupdf 1.24.11
- presidio-analyzer / presidio-anonymizer 2.2.355
- rapidfuzz 3.9.7
- usaddress 0.5.10
- pytesseract 0.3.13
- typer 0.15.2
- pydantic 2.9.2
- cryptography 43.0.3
- keyring 25.5.0

[0.1.0]: https://github.com/tjndr/redactron/releases/tag/v0.1.0
