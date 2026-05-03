# Redactron — Tasks

## Milestone M1 — Core engine (Days 1–4)

### M1.1 Repo scaffolding
**Linear:** BLD-1 | **Model:** haiku | **Type:** infra

Set up pyproject.toml with locked stack, AGPL LICENSE, src/ layout, ruff/mypy config.

- `uv init`; configure pyproject.toml with all deps from tech.md
- ruff: 100-char line length, isort enabled
- mypy: strict for `src/`, lenient for `tests/`
- Skeleton: `src/redactron/__init__.py`, `errors.py`, `config.py`

Files: `pyproject.toml`, `LICENSE`, `.gitignore`, `src/redactron/__init__.py`,
`src/redactron/errors.py`, `src/redactron/config.py`

---

### M1.2 GitHub Actions CI
**Linear:** BLD-2 | **Model:** haiku | **Type:** infra

Matrix CI: Python 3.11 + 3.12, ubuntu-latest + macos-latest.

- `.github/workflows/ci.yml`: checkout → uv setup → install → ruff → mypy → pytest
- Cache uv virtualenv

Files: `.github/workflows/ci.yml`

---

### M1.3 PyMuPDF text extraction with bounding boxes
**Linear:** BLD-3 | **Model:** sonnet | **Type:** feature

Extract text with char-level bounding boxes using `page.get_text("rawdict")`.

- `TextLayer` dataclass: `page_num`, `text`, `bbox`, `block_type`
- Return `List[TextLayer]` per page
- Handle encrypted PDFs with `ExtractionError`

Files: `src/redactron/extract/text_layer.py`, `tests/test_extract.py`

---

### M1.4 Presidio detector wrapper
**Linear:** BLD-4 | **Model:** sonnet | **Type:** feature

Wrap Presidio `AnalyzerEngine`; map results back to bounding boxes.

- `Detection` dataclass: `text`, `entity_type`, `start`, `end`, `score`, `page_num`, `bbox`
- Pure function: `List[TextLayer] → List[Detection]`
- Entities from `profile.detection.presidio_entities`

Files: `src/redactron/detect/presidio_detector.py`, `tests/test_detect.py`

---

### M1.5 PyMuPDF redaction engine
**Linear:** BLD-5 | **Model:** sonnet | **Type:** feature

Apply `page.add_redact_annot()` + `page.apply_redactions()` for each detection.

- Accept `fitz.Document` + `List[Detection]`; never mutate original
- Raise `RedactionError` on failure
- Verification assertion in tests: re-extract confirms target absent

Files: `src/redactron/redact/engine.py`, `tests/test_redact.py`

---

### M1.6 CLI shell with Typer
**Linear:** BLD-6 | **Model:** sonnet | **Type:** feature

Wire `init` and `run` (single-file) commands; orchestration only.

- `redactron init`: create `~/.redactron/profile.yaml`
- `redactron run <path>`: extract → detect → redact → verify pipeline
- Flags: `--profile`, `--output`, `--threshold`, `--ocr`, `--no-verify`, `--json`, `--debug`

Files: `src/redactron/cli.py`

---

## Milestone M2 — Profile + variants (Days 5–7)

### M2.1 Profile schema with Pydantic v2
**Linear:** BLD-7 | **Model:** haiku | **Type:** feature

Pydantic v2 models for profile.yaml; YAML loader/saver.

- Models: `Profile`, `Subject`, `AccountNumber`, `CustomPattern`, `DetectionConfig`
- `load_profile(path) → Profile`; `save_profile(profile, path)`
- Raise `ProfileValidationError` on invalid input

Files: `src/redactron/profile.py`

---

### M2.2 Name variant matching
**Linear:** BLD-8 | **Model:** sonnet | **Type:** feature

Fuzzy name matching with rapidfuzz `token_set_ratio`.

- Match all aliases from profile against each TextLayer
- Threshold from `profile.detection.match_threshold` (default 0.85)
- `full_token_min_length: 2` to avoid over-redaction

Files: `src/redactron/detect/name_detector.py`, `tests/test_detect.py`

---

### M2.3 Address normalization and variant search
**Linear:** BLD-9 | **Model:** sonnet | **Type:** feature

Normalize with `usaddress`; fuzzy match variants.

- Parse profile addresses with `usaddress.tag()`
- Normalize abbreviations (St/Street, Ave/Avenue, etc.)
- "100 Phillip Street" must match "100 Philip St"

Files: `src/redactron/detect/address_detector.py`, `tests/test_detect.py`

---

### M2.4 Account number partial redaction
**Linear:** BLD-10 | **Model:** sonnet | **Type:** feature

Redact all-but-last-N digits; preserve last 4 as plain text.

- 1234-5678-9012-3456 → XXXX-XXXX-XXXX-3456
- Handle hyphenated and plain formats
- `preserve_last=0` redacts entire number

Files: `src/redactron/redact/partial.py`, `tests/test_redact.py`

---

### M2.5 Custom regex patterns from profile
**Linear:** BLD-11 | **Model:** haiku | **Type:** feature

Compile and apply `profile.subject.custom_patterns` regexes.

- Validate regex at profile load time
- Pattern name used as `entity_type` in Detection
- PT-123456 matches `PT-\d{6}`

Files: `src/redactron/detect/account_detector.py`, `tests/test_detect.py`

---

### M2.6 Batch folder processing with progress bar
**Linear:** BLD-12 | **Model:** haiku | **Type:** feature

Process a directory of PDFs with `rich.progress`.

- Glob `*.pdf` recursively; `--output` dir mirrors input structure
- Summary table at end: file, items_redacted, verification_passed

Files: `src/redactron/cli.py`

---

## Milestone M3 — Verification + audit (Days 8–10)

### M3.1 Verifier module
**Linear:** BLD-13 | **Model:** sonnet | **Type:** feature

Re-extract + re-detect post-redaction; return `VerificationResult`.

- `VerificationResult`: `passed: bool`, `survivors: List[Detection]`, `duration_ms: int`
- Raise `VerificationError` if survivors found (unless `--no-verify`)

Files: `src/redactron/verify/verifier.py`, `tests/test_verify.py`

---

### M3.2 SQLite audit log
**Linear:** BLD-14 | **Model:** haiku | **Type:** feature

Persist per-run records; schema migrations.

- `documents` + `subjects` tables per data model
- `log_run(doc_record)` inserts row; upserts subject stats
- DB path: `~/.redactron/audit.db` (override via `REDACTRON_DB`)

Files: `src/redactron/audit/log.py`

---

### M3.3 Subjects table and --subject flag
**Linear:** BLD-15 | **Model:** haiku | **Type:** feature

Multi-subject mode; `redactron subject add|list|show`.

- `--subject <slug>` tags audit rows
- `redactron log --subject <id>` filters correctly

Files: `src/redactron/audit/log.py`, `src/redactron/cli.py`

---

### M3.4 Markdown report generator
**Linear:** BLD-16 | **Model:** haiku | **Type:** feature

Write `<output>.report.md` + `<output>.report.json` alongside redacted PDF.

- Report: filename, pages, items detected/redacted, verification status, survivors
- `redactron report <run_id>` re-renders from audit DB

Files: `src/redactron/report/markdown.py`, `src/redactron/cli.py`

---

### M3.5 Dry-run mode with diff preview
**Linear:** BLD-17 | **Model:** sonnet | **Type:** feature

Run extract+detect only; print detection table; no output written.

- `redactron dry-run <path>`: table of page, entity_type, matched_text, confidence
- Exit 0 if detections found; exit 1 if none

Files: `src/redactron/cli.py`

---

### M3.6 verify and log CLI commands
**Linear:** BLD-18 | **Model:** haiku | **Type:** feature

`redactron verify <path>` and `redactron log` commands.

- `verify`: exit 0 on clean, exit 1 on survivors
- `log`: last 20 runs by default; `--subject`, `--json` flags

Files: `src/redactron/cli.py`

---

## Milestone M3.5 — Encrypted multi-client profile vault (security, Days 11–13)

### M3.5.1 Encrypted vault file format + key management abstraction
**Linear:** BLD-29 | **Model:** sonnet | **Type:** feat

## Goal
Implement AES-256-GCM encrypted vault file with per-vault salt, KDF, and a pluggable
keychain backend interface.

## Implementation notes
- Vault file: `~/.redactron/vault.enc` (AES-256-GCM ciphertext)
- Salt file: `~/.redactron/vault.salt` (random, per-vault, stored plaintext)
- KDF: Argon2id (or HKDF) deriving encryption key from master secret retrieved via keychain
- `KeychainBackend` abstract base class with `get_master_key() → bytes` and
  `set_master_key(key: bytes) → None`
- `VaultStore` class: `open(backend) → Vault`, `seal(vault, backend) → None`
- Profile entry schema: `client_id` (slug PK), `display_name`, `created_at`,
  `updated_at`, `profile_json` (full Profile struct serialized), `notes` (encrypted)
- Raise `VaultError` (new typed exception in `redactron.errors`) on any crypto failure

## Files touched
- `src/redactron/vault/__init__.py`
- `src/redactron/vault/store.py`
- `src/redactron/vault/keychain.py` (abstract base + `KeychainBackend` interface)
- `src/redactron/errors.py` (add `VaultError`)
- `tests/test_vault.py`

## Acceptance criteria
- [ ] Unit tests pass
- [ ] mypy strict passes for affected modules
- [ ] `vault.enc` is opaque ciphertext (`cat vault.enc | strings` shows no plaintext PII)
- [ ] Re-opening vault with correct key returns identical plaintext
- [ ] Wrong key raises `VaultError`

## Model preference
sonnet

## Linked spec
.kiro/specs/redactron/tasks.md#m351-encrypted-vault-file-format--key-management-abstraction

---

### M3.5.2 macOS Keychain Services integration with Touch ID
**Linear:** BLD-30 | **Model:** sonnet | **Type:** feat

## Goal
Implement macOS Keychain backend using the `keyring` library with biometric access
control; stub Linux/Windows backends with `NotImplementedError`.

## Implementation notes
- `MacOSKeychainBackend(KeychainBackend)`: uses `keyring` with macOS-specific
  `kSecAccessControlBiometryAny` access control flag
- Touch ID prompt fires on every `get_master_key()` call (no caching)
- `LinuxKeychainBackend` and `WindowsKeychainBackend`: raise `NotImplementedError`
  with message "Keychain backend not yet supported on <platform>; available in v1.1"
- `get_keychain_backend() → KeychainBackend` factory: auto-detects platform via
  `sys.platform`
- `redactron vault init`: generates 32-byte random master key, stores in keychain,
  creates `vault.enc` + `vault.salt`

## Files touched
- `src/redactron/vault/keychain.py`
- `tests/test_keychain.py`

## Acceptance criteria
- [ ] Unit tests pass (macOS backend mocked; stubs raise NotImplementedError)
- [ ] mypy strict passes
- [ ] Touch ID prompts on every vault access on macOS (verified in integration test)
- [ ] Touch ID overhead < 2 seconds added to typical run

## Model preference
sonnet

## Linked spec
.kiro/specs/redactron/tasks.md#m352-macos-keychain-services-integration-with-touch-id

---

### M3.5.3 Multi-client profile CRUD commands
**Linear:** BLD-31 | **Model:** sonnet | **Type:** feat

## Goal
Implement `profile add/list/show/edit/delete/rename` CLI commands with masked output
by default and Touch ID–gated `--reveal`.

## Implementation notes
- `redactron profile add --client <id>`: interactive prompts or `--import <yaml>`
- `redactron profile list`: shows `client_id` + `display_name` only (no PII)
- `redactron profile show <id>`: masked by default; `--reveal` requires Touch ID + TTY
- `redactron profile edit <id>`: opens `$EDITOR` with decrypted YAML; re-encrypts on save
- `redactron profile delete <id>`: confirmation prompt; secure-wipes entry
- `redactron profile rename <id> <new-id>`: renames slug, preserves data
- All commands load vault via `VaultStore` + `get_keychain_backend()`

## Files touched
- `src/redactron/cli.py`
- `src/redactron/vault/store.py`

## Acceptance criteria
- [ ] Unit tests pass
- [ ] mypy strict passes
- [ ] `profile list` shows no plaintext PII
- [ ] `profile show --reveal` requires Touch ID on macOS
- [ ] `profile show` without `--reveal` shows masked values

## Model preference
sonnet (show/reveal logic); haiku (boilerplate CRUD)

## Linked spec
.kiro/specs/redactron/tasks.md#m353-multi-client-profile-crud-commands

---

### M3.5.4 Migration from single profile.yaml
**Linear:** BLD-32 | **Model:** sonnet | **Type:** feat

## Goal
Implement `profile import <yaml> --client <id>` to migrate legacy `profile.yaml`
into the vault with secure-wipe of the source file.

## Implementation notes
- `redactron profile import old.yaml --client <id>`: reads YAML, validates with
  Pydantic, inserts into vault, then secure-wipes source
- Secure-wipe: overwrite file with random bytes (3 passes), then `unlink`
- `--dry-run`: preview what would be imported without writing or wiping
- Idempotent: if `client_id` already exists, prompt to overwrite or skip
- `src/redactron/vault/migrate.py`: `migrate_profile(path, client_id, vault, dry_run)`

## Files touched
- `src/redactron/vault/migrate.py`
- `src/redactron/cli.py`
- `tests/test_migration.py`

## Acceptance criteria
- [ ] Unit tests pass
- [ ] mypy strict passes
- [ ] Source file is unreadable after import (secure-wipe verified)
- [ ] `--dry-run` writes nothing and wipes nothing
- [ ] Idempotent: re-running with same client_id prompts rather than silently overwriting

## Model preference
sonnet

## Linked spec
.kiro/specs/redactron/tasks.md#m354-migration-from-single-profileyaml

---

### M3.5.5 CLI --client flag on all profile-using commands
**Linear:** BLD-33 | **Model:** haiku | **Type:** feat

## Goal
Add `--client <id>` flag to `run`, `dry-run`, `verify`, `log`, and `profile show|edit`
commands; legacy `profile.yaml` fallback with deprecation warning; default client = "default".

## Implementation notes
- `--client <id>` on `run`/`dry-run`/`verify`: loads profile from vault for given client
- `--client` on `log`: filters audit rows by `client_id`
- Legacy fallback: if `~/.redactron/profile.yaml` exists and `--client` not given,
  load it with `DeprecationWarning: profile.yaml is deprecated; migrate with
  'redactron profile import'`
- Default client slug: `"default"` (used when vault exists but `--client` omitted)
- `get_profile(client_id, vault) → Profile` helper in `vault/store.py`

## Files touched
- `src/redactron/cli.py`
- `src/redactron/vault/store.py`

## Acceptance criteria
- [ ] Unit tests pass
- [ ] mypy strict passes
- [ ] `redactron run doc.pdf --client acme` loads correct profile via Touch ID
- [ ] Legacy `profile.yaml` triggers deprecation warning
- [ ] All existing detection tests pass against vault-loaded profiles

## Model preference
haiku

## Linked spec
.kiro/specs/redactron/tasks.md#m355-cli---client-flag-on-all-profile-using-commands

---

### M3.5.6 SECURITY.md + PROFILE.md vault section + integration tests
**Linear:** BLD-34 | **Model:** haiku | **Type:** docs/test

## Goal
Write `docs/SECURITY.md`, add vault section to `docs/PROFILE.md`, and implement
end-to-end integration tests verifying zero plaintext on disk and Touch ID overhead.

## Implementation notes
- `docs/SECURITY.md`: threat model, vault design, key management, secure-wipe procedure,
  platform support matrix, responsible disclosure
- `docs/PROFILE.md` vault section: vault init, profile add/import, `--client` usage
- Integration test: init vault → add 2 profiles → run with each → assert zero plaintext
  PII in `vault.enc`, swap, temp files, and core dump path
- Performance test: Touch ID overhead < 2 seconds (mocked in CI; real on macOS)
- Zero plaintext assertion: `strings vault.enc | grep -i <known_pii>` returns empty

## Files touched
- `docs/SECURITY.md`
- `docs/PROFILE.md`
- `tests/test_vault.py` (integration tests appended)

## Acceptance criteria
- [ ] Unit + integration tests pass
- [ ] mypy strict passes
- [ ] `cat vault.enc | strings` shows no plaintext PII
- [ ] Touch ID overhead < 2 seconds in perf test
- [ ] All existing detection tests pass

## Model preference
haiku

## Linked spec
.kiro/specs/redactron/tasks.md#m356-securitymd--profilemd-vault-section--integration-tests

---

## Milestone M4 — Polish + launch (Days 11–14)

### M4.1 OCR fallback via pytesseract
**Linear:** BLD-19 | **Model:** sonnet | **Type:** feature

Detect image-only pages; render at 300 DPI; OCR with pytesseract; paint regions.

- `pytesseract.image_to_data()` for word-level bboxes
- Map OCR bboxes to PDF coordinates
- Flag low-confidence words (conf < 60)

Files: `src/redactron/extract/ocr.py`, `tests/test_extract.py`

---

### M4.2 Synthetic test corpus
**Linear:** BLD-20 | **Model:** haiku | **Type:** tests

10 synthetic PDFs with known PII; end-to-end tests assert all PII absent post-redaction.

Document types: bank statement, utility bill, medical record, tax form, insurance EOB,
court doc, payslip, lab report, invoice, leasing agreement.

Files: `tests/fixtures/` (10 PDFs), `tests/test_e2e.py`

---

### M4.3 Docs: README, PROFILE.md, PRIVACY.md, demo GIF
**Linear:** BLD-21 | **Model:** haiku | **Type:** docs

User-facing documentation and demo GIF.

- README: quickstart, feature list, performance targets, screenshots
- PROFILE.md: full profile.yaml field reference
- PRIVACY.md: local-only guarantee, AGPL note, no telemetry

Files: `README.md`, `docs/PROFILE.md`, `docs/PRIVACY.md`, `CHANGELOG.md`

---

### M4.4 PyPI release flow
**Linear:** BLD-22 | **Model:** haiku | **Type:** infra

GitHub Actions release workflow with OIDC trusted publishing.

- `.github/workflows/release.yml`: trigger on `v*` tag; build with hatch; publish
- Configure PyPI trusted publisher (no API token)

Files: `.github/workflows/release.yml`, `pyproject.toml`

---

## Milestone M5 — Web UI (v1.5, Backlog)

### M5.1 Gradio app skeleton
**Linear:** BLD-23 | **Model:** sonnet | **Type:** feature

`gr.Blocks` layout: file upload + run button + download.

Files: `src/redactron/web/app.py`

---

### M5.2 Visual diff preview
**Linear:** BLD-24 | **Model:** sonnet | **Type:** feature

Before/after side-by-side page images with redacted region overlay.

Files: `src/redactron/web/app.py`

---

### M5.3 Profile editor in web UI
**Linear:** BLD-25 | **Model:** haiku | **Type:** feature

Load/edit/save profile.yaml from web form with Pydantic validation.

Files: `src/redactron/web/app.py`

---

### M5.4 Audit log viewer in web UI
**Linear:** BLD-26 | **Model:** haiku | **Type:** feature

Filterable `gr.Dataframe` table by subject and date range.

Files: `src/redactron/web/app.py`

---

### M5.5 redactron ui CLI command
**Linear:** BLD-27 | **Model:** haiku | **Type:** feature

Lazy-import Gradio; launch on localhost:7860; auto-open browser.

Files: `src/redactron/cli.py`, `src/redactron/web/app.py`

---

### M5.6 Web UI screenshots and pip install redactron[ui]
**Linear:** BLD-28 | **Model:** haiku | **Type:** docs

Screenshots in README; finalize `[ui]` optional extra.

Files: `README.md`, `pyproject.toml`, `CHANGELOG.md`, `docs/screenshots/`
