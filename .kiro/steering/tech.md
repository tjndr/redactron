# Tech

## Stack (locked for v1)
- Python 3.11+
- PyMuPDF (fitz) — PDF redaction
- Microsoft Presidio — PII detection
- rapidfuzz — fuzzy match
- usaddress + libpostal — address parsing
- pytesseract — OCR fallback
- Typer — CLI
- Pydantic v2 — schema
- SQLite (stdlib) — audit
- pytest + ruff + mypy — quality
- uv + hatch — packaging

## Constraints
- No cloud calls, ever, in the redaction pipeline
- All third-party libraries must be pip-installable; no system deps beyond Tesseract
- Tests must pass on Linux + macOS in CI
- Type-hinted everywhere; mypy strict mode for `src/redactron/`
- Conventional commits, semantic versioning

## Performance targets (v1)
- 10-page text PDF: < 3 seconds end-to-end including verification
- 10-page image PDF (OCR): < 30 seconds
- Memory: < 500 MB peak per document