"""Tests for MacOSKeychainBackend with LAContext Touch ID gate."""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

from redactron.errors import VaultError


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_get_or_create_calls_touch_id_then_keychain() -> None:
    """Touch ID is called before keychain access."""
    from redactron.vault.keychain_macos import MacOSKeychainBackend

    touch_id_called = []

    def fake_touch_id() -> None:
        touch_id_called.append(True)

    existing_key = os.urandom(32)
    with (
        patch("redactron.vault.keychain_macos._require_touch_id", side_effect=fake_touch_id),
        patch("keyring.get_password", return_value=existing_key.hex()),
    ):
        backend = MacOSKeychainBackend()
        key = backend.get_or_create_master_key("test-vault")

    assert touch_id_called, "Touch ID was not called"
    assert key == existing_key


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_touch_id_failure_raises_vault_error() -> None:
    """If Touch ID fails, VaultError is raised and keychain is not accessed."""
    from redactron.vault.keychain_macos import MacOSKeychainBackend

    with (
        patch(
            "redactron.vault.keychain_macos._require_touch_id",
            side_effect=VaultError("Touch ID authentication failed or was cancelled."),
        ),
        patch("keyring.get_password") as mock_get,
    ):
        backend = MacOSKeychainBackend()
        with pytest.raises(VaultError, match="cancelled"):
            backend.get_or_create_master_key("test-vault")
        mock_get.assert_not_called()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_cache_skips_touch_id_on_second_call() -> None:
    """Second call within same instance uses cache — no Touch ID re-prompt."""
    from redactron.vault.keychain_macos import MacOSKeychainBackend

    touch_id_count = []

    def fake_touch_id() -> None:
        touch_id_count.append(1)

    existing_key = os.urandom(32)
    with (
        patch("redactron.vault.keychain_macos._require_touch_id", side_effect=fake_touch_id),
        patch("keyring.get_password", return_value=existing_key.hex()),
    ):
        backend = MacOSKeychainBackend()
        backend.get_or_create_master_key("test-vault")
        backend.get_or_create_master_key("test-vault")

    assert len(touch_id_count) == 1, "Touch ID called more than once (cache not working)"


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_generates_and_stores_new_key() -> None:
    """First call generates a 32-byte key and stores it."""
    from redactron.vault.keychain_macos import MacOSKeychainBackend

    with (
        patch("redactron.vault.keychain_macos._require_touch_id"),
        patch("keyring.get_password", return_value=None),
        patch("keyring.set_password") as mock_set,
    ):
        backend = MacOSKeychainBackend()
        key = backend.get_or_create_master_key("test-vault")

    assert len(key) == 32
    mock_set.assert_called_once()
    assert bytes.fromhex(mock_set.call_args[0][2]) == key


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_delete_removes_from_cache_and_keychain() -> None:
    from redactron.vault.keychain_macos import MacOSKeychainBackend

    with (
        patch("redactron.vault.keychain_macos._require_touch_id"),
        patch("keyring.get_password", return_value=os.urandom(32).hex()),
        patch("keyring.delete_password") as mock_del,
    ):
        backend = MacOSKeychainBackend()
        backend.get_or_create_master_key("test-vault")
        backend.delete_master_key("test-vault")

    assert "test-vault" not in backend._cache
    mock_del.assert_called_once()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_require_touch_id_fires_real_prompt() -> None:
    """Smoke test: _require_touch_id() fires a real Touch ID prompt.

    This test actually prompts for Touch ID. Run manually to verify.
    Skipped in CI via REDACTRON_REAL_HW guard.
    """
    if not os.environ.get("REDACTRON_REAL_HW"):
        pytest.skip("Set REDACTRON_REAL_HW=1 to run real Touch ID test")

    from redactron.vault.keychain_macos import _require_touch_id
    _require_touch_id()  # Should prompt for Touch ID and succeed
