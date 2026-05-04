# Changelog

All notable changes to redactron are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.2] — 2026-05-04

### Fixed

- Profile template `account_numbers` field now uses block sequence format instead of `[]`, so users can uncomment the example directly without restructuring the YAML.
- README profile example uses a realistic account number (`0021305789Q834`) matching the template example.

### Changed

- Removed `.kiro/`, `.redactron/`, and `scripts/` from repository history. These contained internal tooling, prompts, and credit-tracking scripts that are not part of the build or usable product.

## [0.1.1] — 2026-05-04

### Fixed

- `profile add --from` now secure-wipes the source YAML after vault write. Use `--keep-source` to opt out. (BLD-FIX-31)
- `profile edit` crashed with `ValidationError` when the profile had a minimal schema. Fixed by using a hardcoded defaults dict instead of Pydantic instantiation. (BLD-FIX-34)

### Changed

- OCR auto-triggers by default on image-only pages. Use `--no-ocr` to disable, `--force-ocr` to OCR every page.
- `redactron init` no longer creates `~/.redactron/profile.yaml`. It creates the directory and audit database only. Use `profile add --from` with the template instead.
- Batch outputs go to `{input_dir}/redacted/`. Consolidated batch summary written to `{input_dir}/redacted-reports/`.
- `--version` / `-V` top-level flag added. `redactron version` subcommand still works.
- ASCII banner added to `run` and `version` output. Suppressed by `--quiet`, `--json`, or `NO_COLOR`.
- `profile edit` pre-populates all schema fields with empty defaults so the full schema is visible.
- `$EDITOR` parsed with `shlex.split` so editors with arguments (e.g. `code --wait`) work correctly.
- Numeric span routing and OCR auto-trigger downgraded from `log.warning` to `log.debug`. A successful run at default log level produces no log output.

### Added

- `docs/examples/profile-template.yaml`: full annotated schema for the template-first workflow.
- `--per-file-reports` flag on `run` (default off; consolidated report only).
- `--keep-source` and `--dry-run` flags on `profile add --from`.

## [0.1.0] — 2026-05-03

First public release. Covers milestones M1 through M4 and M3.5.

### Added

**M1 — Core engine**
- PyMuPDF text extraction with character-level bounding boxes (`extract/text_layer.py`)
- Name fuzzy-match detector via rapidfuzz (`detect/name_detector.py`)
- Address detector via usaddress with multi-line bridge (`detect/address_detector.py`)
- Account number / custom regex detector (`detect/account_detector.py`)
- Presidio NLP detector with configurable entities (`detect/presidio_detector.py`)
- Redaction engine with bbox sanity guards. Rejects rects covering more than 30% of page area or taller than 4x median line height. (`redact/engine.py`)
- Partial-match account number redaction with `preserve_last` (`redact/partial.py`)
- Post-redaction verification. Re-scans output and reports survivors. (`verify/verifier.py`)
- Safety-net multi-pass pipeline. Up to 3 passes until no survivors. (`pipeline.py`)

**M2 — Profile + variants**
- Pydantic v2 profile schema with full validation (`profile.py`)
- `redactron init`
- `redactron run` with progress bar
- `redactron dry-run`
- `redactron verify`
- Batch mode: `redactron run ./docs/` redacts entire directories
- JSON output mode (`--json`) for scripting
- Audit log: SQLite record of every run (`audit/log.py`)
- Markdown report generation (`report/markdown.py`)

**M3 — Verification + audit**
- `redactron log`
- `redactron report <id>`
- `redactron subject add/list/show`

**M3.5 — Encrypted multi-client vault**
- AES-256-GCM encrypted vault (`vault/store.py`, `vault/keychain.py`)
- macOS Keychain integration with Touch ID via LocalAuthentication (`vault/keychain_macos.py`)
- `redactron vault init`
- `redactron profile add/list/show/edit/delete/rename/import`
- `redactron run --client <id>`
- Migration from legacy `profile.yaml` with secure-wipe (`vault/migrate.py`)

**M4 — Polish + launch**
- OCR fallback for image-only PDFs via pytesseract (`extract/ocr.py`). Per-page auto-trigger, 300 DPI render, 72/dpi coordinate conversion, confidence threshold 60, bbox sanity guards.
- Synthetic test corpus: 12 document types, 3 E2E assertions each (`tests/test_corpus.py`)
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

[0.1.2]: https://github.com/tjndr/redactron/releases/tag/v0.1.2
[0.1.1]: https://github.com/tjndr/redactron/releases/tag/v0.1.1
[0.1.0]: https://github.com/tjndr/redactron/releases/tag/v0.1.0
