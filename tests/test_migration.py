"""Tests for profile migration (BLD-32)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from redactron.cli import app
from redactron.vault.migrate import migrate_profile, secure_wipe
from redactron.vault.store import VaultStore

runner = CliRunner()

_SAMPLE_YAML = """\
version: 1
name: default
subject:
  display_name: "Alice Sample"
  aliases: ["Alice"]
  addresses: []
  phones: []
  emails: []
  ssns: []
  account_numbers: []
  custom_patterns: []
detection:
  use_presidio: false
  presidio_entities: []
  fuzzy_match: true
  match_threshold: 0.85
  full_token_min_length: 2
  ocr_fallback: false
"""


class StubBackend:
    def __init__(self) -> None:
        self._keys: dict[str, bytes] = {}

    def get_or_create_master_key(self, vault_id: str) -> bytes:
        if vault_id not in self._keys:
            self._keys[vault_id] = os.urandom(32)
        return self._keys[vault_id]

    def delete_master_key(self, vault_id: str) -> None:
        self._keys.pop(vault_id, None)


def _make_store(tmp_path: Path) -> VaultStore:
    return VaultStore(tmp_path / "vault.enc", StubBackend())


# ---------------------------------------------------------------------------
# secure_wipe
# ---------------------------------------------------------------------------

def test_secure_wipe_removes_file(tmp_path: Path) -> None:
    f = tmp_path / "secret.yaml"
    f.write_text("sensitive data")
    secure_wipe(f)
    assert not f.exists()


def test_secure_wipe_overwrites_content(tmp_path: Path) -> None:
    f = tmp_path / "secret.yaml"
    original = "sensitive data 12345"
    f.write_text(original)
    # Capture content just before unlink by patching unlink
    captured: list[bytes] = []
    original_unlink = Path.unlink

    def patched_unlink(self: Path, missing_ok: bool = False) -> None:  # type: ignore[override]
        captured.append(self.read_bytes())
        original_unlink(self, missing_ok=missing_ok)

    with patch.object(Path, "unlink", patched_unlink):
        secure_wipe(f)

    assert captured, "unlink was not called"
    assert original.encode() not in captured[-1], "Original content still present before unlink"


# ---------------------------------------------------------------------------
# migrate_profile
# ---------------------------------------------------------------------------

def test_migrate_profile_imports_and_wipes(tmp_path: Path) -> None:
    yaml_path = tmp_path / "profile.yaml"
    yaml_path.write_text(_SAMPLE_YAML)
    store = _make_store(tmp_path)

    migrate_profile(yaml_path, "alice", store)

    assert not yaml_path.exists(), "Source file should be wiped"
    profile = store.get_profile("alice")
    assert profile is not None
    assert profile["subject"]["display_name"] == "Alice Sample"


def test_migrate_profile_dry_run_no_write_no_wipe(tmp_path: Path) -> None:
    yaml_path = tmp_path / "profile.yaml"
    yaml_path.write_text(_SAMPLE_YAML)
    store = _make_store(tmp_path)

    result = migrate_profile(yaml_path, "alice", store, dry_run=True)

    assert yaml_path.exists(), "Source file must NOT be wiped in dry-run"
    assert store.get_profile("alice") is None, "Vault must NOT be written in dry-run"
    assert result["subject"]["display_name"] == "Alice Sample"


def test_migrate_profile_idempotent(tmp_path: Path) -> None:
    """Re-running with same client_id updates rather than errors."""
    yaml_path = tmp_path / "profile.yaml"
    yaml_path.write_text(_SAMPLE_YAML)
    store = _make_store(tmp_path)
    store.add_profile("alice", {"subject": {"display_name": "Old"}}, "Old")

    # Write yaml again (it was wiped, so re-create)
    yaml_path.write_text(_SAMPLE_YAML)
    migrate_profile(yaml_path, "alice", store)

    profile = store.get_profile("alice")
    assert profile is not None
    assert profile["subject"]["display_name"] == "Alice Sample"


# ---------------------------------------------------------------------------
# CLI: profile import
# ---------------------------------------------------------------------------

def test_cli_profile_import(tmp_path: Path) -> None:
    yaml_path = tmp_path / "profile.yaml"
    yaml_path.write_text(_SAMPLE_YAML)
    store = _make_store(tmp_path)

    with patch("redactron.cli._get_vault_store", return_value=store):
        result = runner.invoke(
            app, ["profile", "import", str(yaml_path), "--client", "alice"]
        )

    assert result.exit_code == 0
    assert "alice" in result.output
    assert not yaml_path.exists()


def test_cli_profile_import_dry_run(tmp_path: Path) -> None:
    yaml_path = tmp_path / "profile.yaml"
    yaml_path.write_text(_SAMPLE_YAML)
    store = _make_store(tmp_path)

    with patch("redactron.cli._get_vault_store", return_value=store):
        result = runner.invoke(
            app, ["profile", "import", str(yaml_path), "--client", "alice", "--dry-run"]
        )

    assert result.exit_code == 0
    assert "dry-run" in result.output
    assert yaml_path.exists(), "Source must not be wiped in dry-run"
    assert store.get_profile("alice") is None


def test_cli_profile_import_default_client_id(tmp_path: Path) -> None:
    """Default client_id is the filename stem."""
    yaml_path = tmp_path / "myprofile.yaml"
    yaml_path.write_text(_SAMPLE_YAML)
    store = _make_store(tmp_path)

    with patch("redactron.cli._get_vault_store", return_value=store):
        result = runner.invoke(app, ["profile", "import", str(yaml_path)])

    assert result.exit_code == 0
    assert store.get_profile("myprofile") is not None


# ---------------------------------------------------------------------------
# Backwards-compat: run command warns when both profile.yaml and vault exist
# ---------------------------------------------------------------------------

def test_run_warns_when_both_exist(tmp_path: Path) -> None:
    """run command emits deprecation warning when both profile.yaml and vault.enc exist."""
    import fitz

    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(_SAMPLE_YAML)
    vault_path = tmp_path / "vault.enc"
    vault_path.write_bytes(b"fake")  # just needs to exist

    pdf_path = tmp_path / "doc.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf_path))

    with (
        patch("redactron.cli._default_vault_path", return_value=vault_path),
        patch("redactron.cli.default_profile_path", return_value=profile_path),
    ):
        result = runner.invoke(app, ["run", str(pdf_path)])

    assert "Deprecation" in result.output or "deprecation" in result.output.lower()
