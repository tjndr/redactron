"""Tests for macOS Keychain backend (BLD-30).

All tests mock the Security/CoreFoundation frameworks — no real keychain access.
The @pytest.mark.macos integration test is skipped in CI (headless).
"""

from __future__ import annotations

import logging
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from redactron.errors import VaultError
from redactron.vault.keychain import (
    LinuxKeychainBackend,
    WindowsKeychainBackend,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_KEY = os.urandom(32)
_VAULT_ID = "test1234abcd5678"


def _mock_macos_backend(key: bytes = _FAKE_KEY) -> MagicMock:
    """Return a MagicMock that behaves like MacOSKeychainBackend."""
    mock = MagicMock()
    store: dict[str, bytes] = {}

    def get_or_create(vault_id: str) -> bytes:
        if vault_id not in store:
            store[vault_id] = key
        return store[vault_id]

    def delete(vault_id: str) -> None:
        store.pop(vault_id, None)

    mock.get_or_create_master_key.side_effect = get_or_create
    mock.delete_master_key.side_effect = delete
    return mock


# ---------------------------------------------------------------------------
# test_linux_backend_raises_notimplemented
# ---------------------------------------------------------------------------

def test_linux_backend_raises_notimplemented() -> None:
    with pytest.raises(NotImplementedError, match="v1.1"):
        LinuxKeychainBackend()


def test_windows_backend_raises_notimplemented() -> None:
    with pytest.raises(NotImplementedError, match="v1.1"):
        WindowsKeychainBackend()


# ---------------------------------------------------------------------------
# test_factory_selects_correct_backend
# ---------------------------------------------------------------------------

def test_factory_linux_raises() -> None:
    with patch("sys.platform", "linux"):
        import importlib

        import redactron.vault.keychain as kc
        importlib.reload(kc)
        with pytest.raises(NotImplementedError):
            kc.get_keychain_backend()
        importlib.reload(kc)


def test_factory_win32_raises() -> None:
    with patch("sys.platform", "win32"):
        import importlib

        import redactron.vault.keychain as kc
        importlib.reload(kc)
        with pytest.raises(NotImplementedError):
            kc.get_keychain_backend()
        importlib.reload(kc)


def test_factory_unknown_platform_raises() -> None:
    with patch("sys.platform", "haiku-os"):
        import importlib

        import redactron.vault.keychain as kc
        importlib.reload(kc)
        with pytest.raises(NotImplementedError, match="haiku-os"):
            kc.get_keychain_backend()
        importlib.reload(kc)


def test_factory_darwin_returns_macos_backend() -> None:
    """On darwin, factory returns MacOSKeychainBackend."""
    import importlib
    import sys as _sys
    import types

    mock_backend = _mock_macos_backend()
    mock_module = types.ModuleType("redactron.vault.keychain_macos")
    mock_module.MacOSKeychainBackend = lambda: mock_backend  # type: ignore[attr-defined]

    with patch.dict(_sys.modules, {"redactron.vault.keychain_macos": mock_module}):
        with patch("sys.platform", "darwin"):
            import redactron.vault.keychain as kc
            importlib.reload(kc)
            backend = kc.get_keychain_backend()
            assert backend is mock_backend
            importlib.reload(kc)


# ---------------------------------------------------------------------------
# test_macos_backend_get_creates_key (mock Security framework)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_macos_backend_get_creates_key_mocked() -> None:
    """First call generates 32-byte key; second call returns same key."""
    from redactron.vault.keychain_macos import MacOSKeychainBackend

    stored: dict[str, bytes] = {}

    def fake_item_copy(query: object, result_ptr: object) -> int:
        # Simulate item not found on first call
        return -25300  # errSecItemNotFound

    def fake_item_add(item: object, result_ptr: object) -> int:
        return 0  # errSecSuccess

    with (
        patch.object(MacOSKeychainBackend, "_retrieve_key", side_effect=VaultError("not found")),
        patch.object(
            MacOSKeychainBackend, "_store_key",
            side_effect=lambda vid, k: stored.update({vid: k}),
        ),
    ):
        backend = MacOSKeychainBackend()
        key1 = backend.get_or_create_master_key(_VAULT_ID)
        assert len(key1) == 32

        # Second call should return cached value (same key)
        key2 = backend.get_or_create_master_key(_VAULT_ID)
        assert key1 == key2
        # _store_key called exactly once
        assert _VAULT_ID in stored


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_macos_backend_delete_mocked() -> None:
    """delete_master_key removes the key from cache and calls SecItemDelete."""
    from redactron.vault.keychain_macos import MacOSKeychainBackend

    with (
        patch.object(MacOSKeychainBackend, "_retrieve_key", side_effect=VaultError("not found")),
        patch.object(MacOSKeychainBackend, "_store_key"),
    ):
        backend = MacOSKeychainBackend()
        backend.get_or_create_master_key(_VAULT_ID)
        assert _VAULT_ID in backend._cache

        with patch.object(backend, "_sec") as mock_sec:
            mock_sec.SecItemDelete.return_value = 0
            # Patch CF functions to avoid real framework calls
            with patch("redactron.vault.keychain_macos._cf_string", return_value=None):
                with patch("redactron.vault.keychain_macos._cf_release"):
                    with patch.object(
                        backend, "_build_query_dict", return_value=None
                    ):
                        backend.delete_master_key(_VAULT_ID)

        assert _VAULT_ID not in backend._cache


# ---------------------------------------------------------------------------
# test_master_key_not_in_logs
# ---------------------------------------------------------------------------

@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_master_key_not_in_logs(caplog: pytest.LogCaptureFixture) -> None:
    """No 32-byte hex string should appear in log output during keychain ops."""
    from redactron.vault.keychain_macos import MacOSKeychainBackend

    test_key = bytes(range(32))  # known pattern, easy to detect

    with (
        patch.object(MacOSKeychainBackend, "_retrieve_key", return_value=test_key),
        caplog.at_level(logging.DEBUG, logger="redactron.vault.keychain_macos"),
    ):
        backend = MacOSKeychainBackend()
        backend.get_or_create_master_key(_VAULT_ID)

    key_hex = test_key.hex()
    for record in caplog.records:
        assert key_hex not in record.getMessage(), (
            f"Master key hex found in log: {record.getMessage()}"
        )


# ---------------------------------------------------------------------------
# Integration test — real macOS hardware, skipped in headless CI
# ---------------------------------------------------------------------------

@pytest.mark.macos
@pytest.mark.skipif(
    sys.platform != "darwin" or os.environ.get("CI") == "true",
    reason="Requires real macOS hardware with Touch ID; skipped in CI",
)
def test_macos_integration_store_retrieve_real_keychain() -> None:
    """Integration: store and retrieve master key via real macOS Keychain.

    This test triggers a Touch ID prompt (or password fallback).
    Run manually on real hardware: uv run pytest tests/test_keychain.py -m macos -v
    """
    from redactron.vault.keychain_macos import MacOSKeychainBackend

    backend = MacOSKeychainBackend()
    test_vault_id = "redactron-test-integration-bld30"

    # Clean up any leftover from previous runs
    try:
        backend.delete_master_key(test_vault_id)
    except Exception:
        pass

    # Create
    key1 = backend.get_or_create_master_key(test_vault_id)
    assert len(key1) == 32

    # Retrieve (new instance, no cache)
    backend2 = MacOSKeychainBackend()
    key2 = backend2.get_or_create_master_key(test_vault_id)
    assert key1 == key2, "Retrieved key must match stored key"

    # Clean up
    backend.delete_master_key(test_vault_id)
