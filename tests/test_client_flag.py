"""Tests for --client flag on profile-using commands (BLD-33)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import fitz
from typer.testing import CliRunner

from redactron.cli import app
from redactron.vault.store import VaultStore

runner = CliRunner()

_SAMPLE_PROFILE = {
    "version": 1,
    "name": "acme",
    "subject": {
        "display_name": "Acme Corp",
        "aliases": [],
        "addresses": [],
        "phones": [],
        "emails": [],
        "ssns": [],
        "account_numbers": [],
        "custom_patterns": [],
    },
    "detection": {
        "use_presidio": False,
        "presidio_entities": [],
        "fuzzy_match": True,
        "match_threshold": 0.85,
        "full_token_min_length": 2,
        "ocr_fallback": False,
    },
}


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


def _make_pdf(tmp_path: Path, name: str = "doc.pdf") -> Path:
    doc = fitz.open()
    doc.new_page()
    pdf_path = tmp_path / name
    doc.save(str(pdf_path))
    return pdf_path


# ---------------------------------------------------------------------------
# run --client
# ---------------------------------------------------------------------------

def test_run_client_loads_vault_profile(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    store.add_profile("acme", _SAMPLE_PROFILE, "Acme Corp")
    pdf_path = _make_pdf(tmp_path)

    with patch("redactron.cli._get_vault_store", return_value=store):
        result = runner.invoke(
            app,
            ["run", str(pdf_path), "--client", "acme", "--no-verify", "--no-report"],
        )
    assert result.exit_code == 0


def test_run_client_missing_shows_available(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    store.add_profile("alice", {}, "Alice")
    pdf_path = _make_pdf(tmp_path)

    with patch("redactron.cli._get_vault_store", return_value=store):
        result = runner.invoke(
            app, ["run", str(pdf_path), "--client", "ghost"]
        )
    assert result.exit_code == 1
    assert "ghost" in result.output
    assert "not found" in result.output


# ---------------------------------------------------------------------------
# _load_profile_for_client
# ---------------------------------------------------------------------------

def test_load_profile_for_client_success(tmp_path: Path) -> None:
    from redactron.cli import _load_profile_for_client

    store = _make_store(tmp_path)
    store.add_profile("acme", _SAMPLE_PROFILE, "Acme Corp")

    with patch("redactron.cli._get_vault_store", return_value=store):
        profile = _load_profile_for_client("acme")
    assert profile.subject.display_name == "Acme Corp"


def test_load_profile_for_client_missing(tmp_path: Path) -> None:
    import typer

    from redactron.cli import _load_profile_for_client

    store = _make_store(tmp_path)

    with patch("redactron.cli._get_vault_store", return_value=store):
        with patch("redactron.cli.typer.echo"):
            try:
                _load_profile_for_client("ghost")
                assert False, "Should have raised Exit"
            except typer.Exit as e:
                assert e.exit_code == 1
