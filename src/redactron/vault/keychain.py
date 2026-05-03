"""KeychainBackend Protocol and platform stubs for M3.5.

Concrete macOS implementation lives in BLD-30 (keychain_macos.py).
Linux and Windows raise NotImplementedError with a v1.1 pointer.
"""

from __future__ import annotations

import sys
from typing import Protocol, runtime_checkable


@runtime_checkable
class KeychainBackend(Protocol):
    """Abstract interface for OS keychain operations."""

    def get_or_create_master_key(self, vault_id: str) -> bytes:
        """Return the 32-byte master key for vault_id, creating it if absent."""
        ...

    def delete_master_key(self, vault_id: str) -> None:
        """Remove the master key for vault_id from the keychain."""
        ...


class LinuxKeychainBackend:
    """Stub — Linux keychain support is planned for v1.1."""

    def __init__(self) -> None:
        raise NotImplementedError(
            "Linux keychain backend (libsecret/SecretService) is planned for v1.1. "
            "Track at https://github.com/tjndr/redactron/issues/."
        )

    def get_or_create_master_key(self, vault_id: str) -> bytes:  # pragma: no cover
        raise NotImplementedError

    def delete_master_key(self, vault_id: str) -> None:  # pragma: no cover
        raise NotImplementedError


class WindowsKeychainBackend:
    """Stub — Windows keychain support is planned for v1.1."""

    def __init__(self) -> None:
        raise NotImplementedError(
            "Windows keychain backend (DPAPI/Credential Manager) is planned for v1.1. "
            "Track at https://github.com/tjndr/redactron/issues/."
        )

    def get_or_create_master_key(self, vault_id: str) -> bytes:  # pragma: no cover
        raise NotImplementedError

    def delete_master_key(self, vault_id: str) -> None:  # pragma: no cover
        raise NotImplementedError


def get_keychain_backend() -> KeychainBackend:
    """Factory: return the correct backend for the current platform."""
    if sys.platform == "darwin":
        import importlib

        mod = importlib.import_module("redactron.vault.keychain_macos")
        backend: KeychainBackend = mod.MacOSKeychainBackend()
        return backend
    elif sys.platform == "linux":
        return LinuxKeychainBackend()  # raises NotImplementedError
    elif sys.platform == "win32":
        return WindowsKeychainBackend()  # raises NotImplementedError
    else:
        raise NotImplementedError(
            f"No keychain backend available for platform '{sys.platform}'. "
            "Supported: macOS (darwin). Linux/Windows planned for v1.1."
        )
