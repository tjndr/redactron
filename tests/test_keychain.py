"""Tests for keychain backends (BLD-30)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from redactron.vault.keychain import (
    LinuxKeychainBackend,
    WindowsKeychainBackend,
)

_FAKE_KEY = os.urandom(32)
_VAULT_ID = "test1234abcd5678"


def _mock_macos_backend(key: bytes = _FAKE_KEY) -> MagicMock:
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


def test_linux_backend_raises_notimplemented() -> None:
    with pytest.raises(NotImplementedError, match="v1.1"):
        LinuxKeychainBackend()


def test_windows_backend_raises_notimplemented() -> None:
    with pytest.raises(NotImplementedError, match="v1.1"):
        WindowsKeychainBackend()


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
