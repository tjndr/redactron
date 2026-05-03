"""AES-256-GCM encrypted vault store for multi-client profiles (M3.5).

File format (~/.redactron/vault.enc):
  magic   : 8 bytes  b"REDV1\\x00\\x00\\x00"
  nonce   : 12 bytes (random per encryption)
  tag     : 16 bytes (GCM authentication tag)
  cipher  : N bytes  (AES-256-GCM ciphertext of JSON payload)
  Total   = 36 + N bytes

The JSON payload is decrypted in-memory only and never written to disk in
plaintext. The master key lives exclusively in the OS keychain.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from redactron.errors import SecurityError, VaultError
from redactron.vault.keychain import KeychainBackend

_MAGIC = b"REDV1\x00\x00\x00"
_MAGIC_LEN = 8
_NONCE_LEN = 12
_TAG_LEN = 16
_HEADER_LEN = _MAGIC_LEN + _NONCE_LEN + _TAG_LEN  # 36


def _vault_id(path: Path) -> str:
    """Stable, short identifier derived from the vault path (for keychain service name)."""
    return hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:16]


def _enforce_perms(path: Path) -> None:
    """Raise SecurityError if path permissions are looser than 0600."""
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o177:  # any bits beyond owner rw
        raise SecurityError(
            f"Vault file permissions too permissive (mode {oct(mode)}). "
            f"Run: chmod 600 {path}"
        )


def _set_perms(path: Path) -> None:
    """Enforce 0600 on path."""
    path.chmod(0o600)


@dataclass
class ProfileMeta:
    """Lightweight profile summary returned by list_profiles()."""

    client_id: str
    display_name: str
    created_at: str
    updated_at: str


class VaultStore:
    """Encrypted vault backed by AES-256-GCM.

    Args:
        path: Path to vault.enc file (e.g. ~/.redactron/vault.enc).
        backend: KeychainBackend providing the 32-byte master key.
    """

    def __init__(self, path: Path, backend: KeychainBackend) -> None:
        self._path = path
        self._salt_path = path.with_suffix(".salt")
        self._backend = backend
        self._vault_id = _vault_id(path)

    # ------------------------------------------------------------------
    # Low-level crypto
    # ------------------------------------------------------------------

    def _get_key(self) -> bytes:
        key = self._backend.get_or_create_master_key(self._vault_id)
        if len(key) != 32:
            raise VaultError(f"Master key must be 32 bytes, got {len(key)}")
        return key

    def _encrypt(self, plaintext: bytes, key: bytes) -> bytes:
        """Return magic + nonce + tag + ciphertext."""
        nonce = os.urandom(_NONCE_LEN)
        aesgcm = AESGCM(key)
        # AESGCM.encrypt returns ciphertext + tag (tag appended)
        ct_and_tag = aesgcm.encrypt(nonce, plaintext, None)
        # ct_and_tag = ciphertext || tag (last 16 bytes)
        ciphertext = ct_and_tag[:-_TAG_LEN]
        tag = ct_and_tag[-_TAG_LEN:]
        return _MAGIC + nonce + tag + ciphertext

    def _decrypt(self, data: bytes, key: bytes) -> bytes:
        """Parse magic+nonce+tag+ciphertext and return plaintext."""
        if len(data) < _HEADER_LEN:
            raise VaultError("Vault file too short to be valid.")
        magic = data[:_MAGIC_LEN]
        if magic != _MAGIC:
            raise VaultError(f"Invalid vault magic bytes: {magic!r}")
        nonce = data[_MAGIC_LEN : _MAGIC_LEN + _NONCE_LEN]
        tag = data[_MAGIC_LEN + _NONCE_LEN : _HEADER_LEN]
        ciphertext = data[_HEADER_LEN:]
        aesgcm = AESGCM(key)
        try:
            # cryptography expects ciphertext || tag
            return aesgcm.decrypt(nonce, ciphertext + tag, None)
        except Exception as exc:
            raise VaultError("Vault decryption failed — wrong key or tampered data.") from exc

    # ------------------------------------------------------------------
    # Payload helpers
    # ------------------------------------------------------------------

    def _empty_payload(self) -> dict[str, Any]:
        return {"version": 1, "profiles": {}}

    def _now_iso(self) -> str:
        return datetime.now(UTC).isoformat()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open(self) -> dict[str, Any]:
        """Decrypt and return the vault payload dict.

        Creates an empty vault if the file does not exist yet.
        """
        if not self._path.exists():
            return self._empty_payload()
        _enforce_perms(self._path)
        data = self._path.read_bytes()
        key = self._get_key()
        plaintext = self._decrypt(data, key)
        return json.loads(plaintext.decode())  # type: ignore[no-any-return]

    def save(self, payload: dict[str, Any]) -> None:
        """Encrypt payload and atomically write to vault.enc."""
        key = self._get_key()
        plaintext = json.dumps(payload, ensure_ascii=False).encode()
        blob = self._encrypt(plaintext, key)

        # Atomic write: tmp → fsync → rename
        tmp = self._path.with_suffix(".enc.tmp")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(blob)
        _set_perms(tmp)
        # fsync
        with tmp.open("rb") as fh:
            os.fsync(fh.fileno())
        tmp.rename(self._path)
        _set_perms(self._path)

        # Ensure salt file exists and is 0600
        if not self._salt_path.exists():
            self._salt_path.write_bytes(os.urandom(32))
        _set_perms(self._salt_path)

    def add_profile(
        self,
        client_id: str,
        profile: dict[str, Any],
        display_name: str,
        notes: str | None = None,
    ) -> None:
        """Add a new profile entry. Raises VaultError if client_id already exists."""
        payload = self.open()
        if client_id in payload["profiles"]:
            raise VaultError(
                f"Profile '{client_id}' already exists. Use update_profile() to overwrite."
            )
        now = self._now_iso()
        payload["profiles"][client_id] = {
            "display_name": display_name,
            "created_at": now,
            "updated_at": now,
            "profile_json": profile,
            "notes": notes,
        }
        self.save(payload)

    def get_profile(self, client_id: str) -> dict[str, Any] | None:
        """Return the profile_json dict for client_id, or None if not found."""
        payload = self.open()
        entry = payload["profiles"].get(client_id)
        if entry is None:
            return None
        return entry["profile_json"]  # type: ignore[no-any-return]

    def list_profiles(self) -> list[ProfileMeta]:
        """Return lightweight metadata for all profiles (no PII)."""
        payload = self.open()
        return [
            ProfileMeta(
                client_id=cid,
                display_name=entry["display_name"],
                created_at=entry["created_at"],
                updated_at=entry["updated_at"],
            )
            for cid, entry in payload["profiles"].items()
        ]

    def delete_profile(self, client_id: str) -> None:
        """Remove a profile entry. Idempotent (no error if not found)."""
        payload = self.open()
        payload["profiles"].pop(client_id, None)
        self.save(payload)

    def update_profile(self, client_id: str, profile: dict[str, Any]) -> None:
        """Replace profile_json for an existing entry. Raises VaultError if not found."""
        payload = self.open()
        if client_id not in payload["profiles"]:
            raise VaultError(f"Profile '{client_id}' not found.")
        payload["profiles"][client_id]["profile_json"] = profile
        payload["profiles"][client_id]["updated_at"] = self._now_iso()
        self.save(payload)

    def rename_profile(self, old_id: str, new_id: str) -> None:
        """Rename a profile entry. Raises VaultError if old_id not found or new_id exists."""
        payload = self.open()
        if old_id not in payload["profiles"]:
            raise VaultError(f"Profile '{old_id}' not found.")
        if new_id in payload["profiles"]:
            raise VaultError(f"Profile '{new_id}' already exists.")
        entry = payload["profiles"].pop(old_id)
        entry["updated_at"] = self._now_iso()
        payload["profiles"][new_id] = entry
        self.save(payload)
