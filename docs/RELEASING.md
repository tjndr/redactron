# Releasing redactron

## One-time setup: PyPI trusted publisher

Before the first release, configure trusted publishing on PyPI (no API tokens needed):

1. Go to https://pypi.org/manage/account/publishing/
2. Add a new publisher:
   - PyPI project name: `redactron`
   - Owner: `tjndr`
   - Repository: `redactron`
   - Workflow: `release.yml`
   - Environment: `pypi`
3. Repeat on https://test.pypi.org for the `testpypi` environment.

## Cutting a release

### 1. Update version

```bash
# Edit pyproject.toml — bump version field
# Edit CHANGELOG.md — move [Unreleased] items to new version section
```

### 2. Commit and push

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "chore(release): bump version to 0.2.0"
git push origin main
```

### 3. Tag and push

```bash
# Release candidate → TestPyPI
git tag v0.2.0-rc.1
git push origin v0.2.0-rc.1

# Verify TestPyPI install works:
pip install --index-url https://test.pypi.org/simple/ redactron==0.2.0rc1
redactron --version

# Final release → PyPI
git tag v0.2.0
git push origin v0.2.0
```

### 4. Verify

```bash
pip install redactron==0.2.0
redactron --version
```

## Tag pattern

| Tag | Destination |
|---|---|
| `v*.*.*-rc.*` (e.g. `v0.1.0-rc.1`) | TestPyPI |
| `v*.*.*` (e.g. `v0.1.0`) | PyPI |

## Build smoke test

The `release.yml` workflow also runs a build-only job on every push to `main`
(no publish). This catches packaging regressions early — if `uv build` fails,
the CI check fails before any tag is pushed.
