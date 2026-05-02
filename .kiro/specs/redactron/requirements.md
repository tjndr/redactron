# Redactron — Requirements

## User Stories

### US-1 Single-file redaction (M1)
As a privacy-minded individual, I want to run `redactron run document.pdf` so that all PII
matching my profile is permanently removed from the output PDF.

**Acceptance criteria (M1):**
- `redactron run <file.pdf>` produces a redacted output PDF
- Known PII string from profile is absent in output (verified by re-extraction)
- CI passes on Linux + macOS

### US-2 Profile-driven detection (M2)
As a user, I want to define my name aliases, addresses, phone numbers, emails, account numbers,
and custom regex patterns in a YAML profile so that detection is tailored to my data.

**Acceptance criteria (M2):**
- profile.yaml loads and validates without errors
- "100 Phillip Street" matches "100 Philip St" via fuzzy matching
- 1234-5678-9012-3456 redacts to XXXX-XXXX-XXXX-3456
- A folder of 10 mixed PDFs processes in one command

### US-3 Verification and audit (M3)
As a professional, I want every redaction run to produce a verification report and audit log
so that I can prove compliance and review what was redacted.

**Acceptance criteria (M3):**
- Every run produces a markdown + JSON verification report
- Audit log is queryable by `redactron log --subject <id>`
- Dry-run mode shows what would be redacted without writing output

### US-4 OCR and launch (M4)
As a user with scanned documents, I want image-only PDFs to be OCR'd and redacted so that
I can process any PDF regardless of whether it has a text layer.

**Acceptance criteria (M4):**
- Image-only PDF gets OCR'd and redacted
- 10 synthetic test PDFs all pass redaction + verification
- `pip install redactron` works from PyPI
- README quickstart + demo GIF

### US-5 Web UI (M5 — v1.5)
As a non-technical user, I want a browser-based UI so that I can drag-drop files, see a
visual diff, edit my profile, and browse the audit log without using the terminal.

**Acceptance criteria (M5):**
- `redactron ui` opens browser with working Gradio UI
- Drag-drop folder, redact in real time, download zip
- Visual diff overlay per page
- Profile editable via UI
- Audit log filterable by subject and date range

## Non-goals (v1)
- Cloud SaaS or multi-user web app
- Real-time/streaming redaction
- Editing redacted output (permanent by design)
- Tax/legal advice

## Constraints
- Local-only: no network calls in the redaction pipeline
- AGPL-3.0 license (PyMuPDF compatibility)
- Python 3.11+; pip-installable; no system deps beyond Tesseract
- Tests pass on Linux + macOS in CI
