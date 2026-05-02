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
