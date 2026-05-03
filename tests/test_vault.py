"""Tests for src/redactron/vault/store.py and keychain.py (BLD-29).

All tests use a StubBackend that holds the key in memory — no real keychain.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from redactron.errors import SecurityError, VaultError
from redactron.vault.keychain import KeychainBackend, LinuxKeychainBackend, WindowsKeychainBackend
from redactron.vault.store import _HEADER_LEN, VaultStore

# ---------------------------------------------------------------------------
# Stub backend (in-memory, no OS keychain)
# ---------------------------------------------------------------------------

class StubBackend:
    """Minimal KeychainBackend for testing."""

    def __init__(self, key: bytes | None = None) -> None:
        self._keys: dict[str, bytes] = {}
        if key is not None:
            self._default_key = key
        else:
            self._default_key = os.urandom(32)

    def get_or_create_master_key(self, vault_id: str) -> bytes:
        if vault_id not in self._keys:
            self._keys[vault_id] = self._default_key
        return self._keys[vault_id]

    def delete_master_key(self, vault_id: str) -> None:
        self._keys.pop(vault_id, None)


def _store(tmp_path: Path, key: bytes | None = None) -> VaultStore:
    return VaultStore(tmp_path / "vault.enc", StubBackend(key))


# ---------------------------------------------------------------------------
# test_keychain_backend_protocol
# ---------------------------------------------------------------------------

def test_keychain_backend_protocol() -> None:
    """StubBackend satisfies the KeychainBackend Protocol."""
    backend = StubBackend()
    assert isinstance(backend, KeychainBackend)


# ---------------------------------------------------------------------------
# test_linux_backend_raises
# ---------------------------------------------------------------------------

def test_linux_backend_raises() -> None:
    """LinuxKeychainBackend raises NotImplementedError on instantiation."""
    with pytest.raises(NotImplementedError, match="v1.1"):
        LinuxKeychainBackend()


def test_windows_backend_raises() -> None:
    """WindowsKeychainBackend raises NotImplementedError on instantiation."""
    with pytest.raises(NotImplementedError, match="v1.1"):
        WindowsKeychainBackend()


# ---------------------------------------------------------------------------
# test_encrypt_decrypt_roundtrip
# ---------------------------------------------------------------------------

def test_encrypt_decrypt_roundtrip(tmp_path: Path) -> None:
    """Payload survives encrypt → save → open."""
    store = _store(tmp_path)
    payload: dict[str, Any] = {
        "version": 1,
        "profiles": {
            "alice": {
                "display_name": "Alice Example",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "profile_json": {"subject": {"display_name": "Alice Example"}},
                "notes": None,
            }
        },
    }
    store.save(payload)
    recovered = store.open()
    assert recovered == payload


# ---------------------------------------------------------------------------
# test_nonce_uniqueness
# ---------------------------------------------------------------------------

def test_nonce_uniqueness(tmp_path: Path) -> None:
    """1000 encryptions of the same plaintext produce 1000 distinct ciphertexts."""
    store = _store(tmp_path)
    payload: dict[str, Any] = {"version": 1, "profiles": {}}
    blobs: set[bytes] = set()
    for _ in range(1000):
        store.save(payload)
        blobs.add((tmp_path / "vault.enc").read_bytes())
    assert len(blobs) == 1000, "Nonce reuse detected — ciphertexts are not all distinct"


# ---------------------------------------------------------------------------
# test_tampered_ciphertext_raises
# ---------------------------------------------------------------------------

def test_tampered_ciphertext_raises(tmp_path: Path) -> None:
    """Flipping one byte in the ciphertext raises VaultError (GCM auth failure)."""
    store = _store(tmp_path)
    store.save({"version": 1, "profiles": {}})
    vault_path = tmp_path / "vault.enc"
    data = bytearray(vault_path.read_bytes())
    # Flip a byte in the ciphertext region (after header)
    data[_HEADER_LEN] ^= 0xFF
    vault_path.write_bytes(bytes(data))
    vault_path.chmod(0o600)
    with pytest.raises(VaultError, match="decryption failed"):
        store.open()


# ---------------------------------------------------------------------------
# test_wrong_key_raises
# ---------------------------------------------------------------------------

def test_wrong_key_raises(tmp_path: Path) -> None:
    """Decrypting with a different key raises VaultError."""
    key_a = os.urandom(32)
    key_b = os.urandom(32)
    store_a = _store(tmp_path, key_a)
    store_a.save({"version": 1, "profiles": {}})
    store_b = _store(tmp_path, key_b)
    with pytest.raises(VaultError, match="decryption failed"):
        store_b.open()


# ---------------------------------------------------------------------------
# test_no_plaintext_pii_in_vault
# ---------------------------------------------------------------------------

def test_no_plaintext_pii_in_vault(tmp_path: Path) -> None:
    """vault.enc bytes must not contain any profile string in plaintext."""
    store = _store(tmp_path)
    pii_string = "Tejinder Singh Secret SSN 123-45-6789"
    store.save({
        "version": 1,
        "profiles": {
            "client1": {
                "display_name": "Tejinder Singh",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "profile_json": {"subject": {"display_name": pii_string}},
                "notes": None,
            }
        },
    })
    raw = (tmp_path / "vault.enc").read_bytes()
    # Check that none of the PII substrings appear as UTF-8 in the raw bytes
    for fragment in ["Tejinder", "Singh", "123-45-6789", "Secret"]:
        assert fragment.encode() not in raw, (
            f"Plaintext PII fragment '{fragment}' found in vault.enc"
        )


# ---------------------------------------------------------------------------
# test_atomic_write
# ---------------------------------------------------------------------------

def test_atomic_write(tmp_path: Path) -> None:
    """vault.enc.tmp is cleaned up; vault.enc is never left in partial state."""
    store = _store(tmp_path)
    store.save({"version": 1, "profiles": {}})
    # After save, no .tmp file should remain
    tmp_file = tmp_path / "vault.enc.tmp"
    assert not tmp_file.exists(), "Temporary file was not cleaned up after atomic write"
    # vault.enc must exist and be readable
    assert (tmp_path / "vault.enc").exists()


# ---------------------------------------------------------------------------
# test_vault_perms
# ---------------------------------------------------------------------------

def test_vault_perms(tmp_path: Path) -> None:
    """vault.enc and vault.salt are mode 0600 after save."""
    store = _store(tmp_path)
    store.save({"version": 1, "profiles": {}})
    vault_mode = stat.S_IMODE((tmp_path / "vault.enc").stat().st_mode)
    salt_mode = stat.S_IMODE((tmp_path / "vault.salt").stat().st_mode)
    assert vault_mode == 0o600, f"vault.enc mode is {oct(vault_mode)}, expected 0o600"
    assert salt_mode == 0o600, f"vault.salt mode is {oct(salt_mode)}, expected 0o600"


# ---------------------------------------------------------------------------
# test_refuse_load_if_perms_loose
# ---------------------------------------------------------------------------

def test_refuse_load_if_perms_loose(tmp_path: Path) -> None:
    """chmod 0644 on vault.enc raises SecurityError on open()."""
    store = _store(tmp_path)
    store.save({"version": 1, "profiles": {}})
    (tmp_path / "vault.enc").chmod(0o644)
    with pytest.raises(SecurityError, match="permissive"):
        store.open()


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

def test_add_and_get_profile(tmp_path: Path) -> None:
    """add_profile then get_profile returns the same profile_json."""
    store = _store(tmp_path)
    profile = {"subject": {"display_name": "Bob"}}
    store.add_profile("bob", profile, "Bob Example")
    assert store.get_profile("bob") == profile


def test_get_profile_missing_returns_none(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.get_profile("nonexistent") is None


def test_add_duplicate_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.add_profile("bob", {}, "Bob")
    with pytest.raises(VaultError, match="already exists"):
        store.add_profile("bob", {}, "Bob Again")


def test_list_profiles(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.add_profile("alice", {}, "Alice")
    store.add_profile("bob", {}, "Bob")
    metas = store.list_profiles()
    ids = {m.client_id for m in metas}
    assert ids == {"alice", "bob"}
    # No PII in ProfileMeta beyond display_name
    for m in metas:
        assert m.display_name in {"Alice", "Bob"}


def test_delete_profile(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.add_profile("alice", {}, "Alice")
    store.delete_profile("alice")
    assert store.get_profile("alice") is None


def test_delete_profile_idempotent(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.delete_profile("nonexistent")  # must not raise


def test_update_profile(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.add_profile("alice", {"v": 1}, "Alice")
    store.update_profile("alice", {"v": 2})
    assert store.get_profile("alice") == {"v": 2}


def test_update_profile_missing_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(VaultError, match="not found"):
        store.update_profile("ghost", {})


def test_rename_profile(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.add_profile("old", {"v": 1}, "Old Name")
    store.rename_profile("old", "new")
    assert store.get_profile("old") is None
    assert store.get_profile("new") == {"v": 1}


def test_rename_profile_missing_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(VaultError, match="not found"):
        store.rename_profile("ghost", "new")


def test_rename_profile_collision_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.add_profile("a", {}, "A")
    store.add_profile("b", {}, "B")
    with pytest.raises(VaultError, match="already exists"):
        store.rename_profile("a", "b")


# ---------------------------------------------------------------------------
# get_keychain_backend factory
# ---------------------------------------------------------------------------

def test_factory_darwin_imports_macos_backend() -> None:
    """On darwin, factory returns a MacOSKeychainBackend instance."""
    import sys as _sys
    import types

    stub_backend = StubBackend()
    mock_module = types.ModuleType("redactron.vault.keychain_macos")
    mock_module.MacOSKeychainBackend = lambda: stub_backend  # type: ignore[attr-defined]

    with patch.dict(_sys.modules, {"redactron.vault.keychain_macos": mock_module}):
        with patch("sys.platform", "darwin"):
            # Re-import to pick up the patched platform
            import importlib

            import redactron.vault.keychain as kc_mod
            importlib.reload(kc_mod)
            backend = kc_mod.get_keychain_backend()
            assert isinstance(backend, StubBackend)
            # Restore
            importlib.reload(kc_mod)


def test_factory_linux_raises() -> None:
    with patch("sys.platform", "linux"):
        from redactron.vault.keychain import get_keychain_backend
        with pytest.raises(NotImplementedError):
            get_keychain_backend()


def test_factory_win32_raises() -> None:
    with patch("sys.platform", "win32"):
        from redactron.vault.keychain import get_keychain_backend
        with pytest.raises(NotImplementedError):
            get_keychain_backend()


def test_factory_unknown_platform_raises() -> None:
    with patch("sys.platform", "freebsd"):
        from redactron.vault.keychain import get_keychain_backend
        with pytest.raises(NotImplementedError, match="freebsd"):
            get_keychain_backend()
