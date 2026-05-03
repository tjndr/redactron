"""Migration from legacy profile.yaml to encrypted vault (M3.5.4)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from redactron.vault.store import VaultStore


def secure_wipe(path: Path) -> None:
    """Overwrite file with random bytes 3 times, then unlink."""
    size = path.stat().st_size
    for _ in range(3):
        with path.open("wb") as fh:
            fh.write(os.urandom(max(size, 1)))
            fh.flush()
            os.fsync(fh.fileno())
    path.unlink()


def migrate_profile(
    yaml_path: Path,
    client_id: str,
    store: VaultStore,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Validate and migrate a legacy profile.yaml into the vault.

    Args:
        yaml_path: Path to the legacy profile.yaml.
        client_id: Target client ID in the vault.
        store: VaultStore to write into.
        dry_run: If True, validate and preview without writing or wiping.

    Returns:
        The profile dict that was (or would be) imported.

    Raises:
        ProfileValidationError: If the YAML fails Pydantic validation.
        VaultError: If the vault operation fails.
    """
    from redactron.profile import load_profile

    profile_obj = load_profile(yaml_path)
    profile_dict = profile_obj.model_dump(mode="json")
    display_name = profile_obj.subject.display_name

    if dry_run:
        return profile_dict

    # Check if client_id already exists — update rather than error (idempotent)
    existing = store.get_profile(client_id)
    if existing is not None:
        store.update_profile(client_id, profile_dict)
    else:
        store.add_profile(client_id, profile_dict, display_name)

    secure_wipe(yaml_path)
    return profile_dict
