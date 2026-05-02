# Conventions

## Code style
- ruff with default rules + isort
- mypy strict for src/, lenient for tests/
- 100-char line length
- Google-style docstrings on all public functions

## Module boundaries
- `extract/` — read-only PDF parsing
- `detect/` — pure functions: text → list[Detection]
- `redact/` — receives Detection list + PDF, returns redacted PDF
- `verify/` — receives original profile + redacted PDF, returns survivors
- `audit/` — SQLite I/O only
- `cli.py` — only orchestration; no business logic

## Error handling
- Raise typed exceptions from `redactron.errors`
- CLI catches and prints user-friendly errors with `--debug` for stack traces
- Never silently swallow errors during redaction; fail loudly

## Testing
- Each detector has unit tests with 95%+ coverage on its module
- End-to-end tests use synthetic PDFs in tests/fixtures/
- All redaction tests must include a verification assertion
- No live network calls in tests; mock cloud APIs (none expected anyway)

## Git
- Conventional commits: feat, fix, docs, test, chore, refactor
- One Linear issue per PR; reference issue ID in commit footer
- Branch naming: `<phase>/<issue-id>-short-desc` e.g. `m1/m1-3-text-extraction`