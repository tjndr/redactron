# Contributing to redactron

## Dev setup

```bash
git clone https://github.com/tjndr/redactron
cd redactron
uv sync --all-extras
```

Requires: Python 3.11+, [uv](https://github.com/astral-sh/uv), Tesseract (for OCR tests).

## Running tests

```bash
uv run pytest          # full suite with coverage
uv run ruff check      # linter
uv run mypy src/       # type checker (strict)
```

All three must pass before opening a PR.

## Commits

Conventional commits: `feat`, `fix`, `docs`, `test`, `chore`, `refactor`.

```
feat(ocr): add pytesseract fallback for image-only pages (BLD-19)
fix(vault): correct nonce reuse guard on concurrent saves
docs(profile): add numeric-matching gotchas section
```

Reference the Linear issue ID in the commit footer when applicable.

## Pull requests

- One Linear issue per PR.
- Branch naming: `<milestone>/<issue-id>-short-desc` (e.g. `m4/bld-19-ocr-fallback`).
- All tests must pass; no ruff or mypy errors.
- PRs against `main`; squash merge.

## Code style

- ruff with default rules + isort, 100-char line length.
- mypy strict for `src/redactron/`; lenient for `tests/`.
- Google-style docstrings on all public functions.
- No business logic in `cli.py` — orchestration only.
