# Contributing to redactron

## Dev setup

```bash
git clone https://github.com/tjndr/redactron
cd redactron
uv sync --all-extras
```

Requires: Python 3.11+, [uv](https://github.com/astral-sh/uv), Tesseract (for OCR tests on real PDFs).

## Running tests

```bash
uv run pytest          # full suite with coverage
uv run ruff check      # linter
uv run mypy src/       # type checker (strict)
```

All three must pass before opening a PR.

## Branch naming

```
<milestone>/<issue-id>-short-desc
```

Examples:
- `v0.1.1/bld-42-ocr-auto`
- `m4/bld-19-ocr-fallback`

## Conventional commits

Format: `<type>(<scope>): <description> (<issue-id>)`

Types: `feat`, `fix`, `docs`, `test`, `chore`, `refactor`

```
feat(ocr): add pytesseract fallback for image-only pages (BLD-19)
fix(vault): correct nonce reuse guard on concurrent saves (BLD-30)
docs(profile): add numeric-matching gotchas section (BLD-FIX-19)
```

Reference the Linear issue ID in the commit footer when applicable.

## PR process

- One Linear issue per PR.
- All tests must pass; no ruff or mypy errors.
- PRs against `main`; squash merge.
- Auto-merge enabled for most issues. Manual review required for UX-critical changes (batch resilience, progress UI).

## Filing bugs vs features vs security issues

- **Bugs:** Open a GitHub issue with steps to reproduce, expected vs actual behavior, and your OS + Python version.
- **Feature requests:** Open a GitHub issue with the use case and proposed CLI/API shape.
- **Security issues:** Email tejinder.singh@ieee.org. Do not open a public issue. See [docs/SECURITY.md](docs/SECURITY.md) for the disclosure policy.

## Code of conduct

Be respectful. Harassment, discrimination, or personal attacks will not be tolerated. This project follows the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).

## Code style

- ruff with default rules + isort, 100-char line length.
- mypy strict for `src/redactron/`; lenient for `tests/`.
- Google-style docstrings on all public functions.
- No business logic in `cli.py` — orchestration only.
- `log.warning()` reserved for actual problems. Expected behavior (numeric span routing, OCR auto-trigger) uses `log.debug()`.
