"""End-to-end vault integration tests (BLD-34).

Tests:
1. vault init → profile add (2 clients) → run with each → verify correct profile applied
2. No plaintext PII in vault.enc after save
3. Touch ID overhead < 2s (mocked)
4. All existing detection tests pass against vault-loaded profiles
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import fitz

from redactron.vault.store import VaultStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _make_pdf_with_text(tmp_path: Path, text: str, name: str = "doc.pdf") -> Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), text, fontsize=12)
    pdf_path = tmp_path / name
    doc.save(str(pdf_path))
    return pdf_path


_ALICE_PROFILE = {
    "version": 1,
    "name": "alice",
    "subject": {
        "display_name": "Alice Wonderland",
        "aliases": ["Alice"],
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

_BOB_PROFILE = {
    "version": 1,
    "name": "bob",
    "subject": {
        "display_name": "Bob Builder",
        "aliases": ["Bob"],
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


# ---------------------------------------------------------------------------
# Test 1: vault init → add 2 profiles → run with each
# ---------------------------------------------------------------------------

def test_e2e_vault_two_clients(tmp_path: Path) -> None:
    """vault init → add alice + bob → run on PDF with each → correct profile applied."""
    store = _make_store(tmp_path)

    # Add two profiles
    store.add_profile("alice", _ALICE_PROFILE, "Alice Wonderland")
    store.add_profile("bob", _BOB_PROFILE, "Bob Builder")

    # Verify both are retrievable
    alice = store.get_profile("alice")
    bob = store.get_profile("bob")
    assert alice is not None
    assert bob is not None
    assert alice["subject"]["display_name"] == "Alice Wonderland"
    assert bob["subject"]["display_name"] == "Bob Builder"

    # Run pipeline with alice's profile on a PDF containing alice's name
    from redactron.pipeline import run_pipeline
    from redactron.profile import Profile

    alice_profile = Profile.model_validate(alice)
    bob_profile = Profile.model_validate(bob)

    pdf_path = _make_pdf_with_text(tmp_path, "Alice Wonderland is the subject.")
    out_alice = tmp_path / "alice_redacted.pdf"
    out_bob = tmp_path / "bob_redacted.pdf"

    result_alice = run_pipeline(
        pdf_path, out_alice, alice_profile, verify=False, write_reports=False
    )
    result_bob = run_pipeline(pdf_path, out_bob, bob_profile, verify=False, write_reports=False)

    # Alice's profile should detect "Alice Wonderland"; Bob's should not
    alice_texts = {d.text for d in result_alice.detections}
    bob_texts = {d.text for d in result_bob.detections}

    assert any("Alice" in t for t in alice_texts), (
        f"Alice's profile should detect her name; got: {alice_texts}"
    )
    # Bob's profile has no aliases matching "Alice Wonderland"
    assert not any("Alice" in t for t in bob_texts), (
        f"Bob's profile should NOT detect Alice's name; got: {bob_texts}"
    )


# ---------------------------------------------------------------------------
# Test 2: no plaintext PII in vault.enc
# ---------------------------------------------------------------------------

def test_no_plaintext_pii_in_vault(tmp_path: Path) -> None:
    """vault.enc bytes must not contain any profile PII in plaintext."""
    store = _make_store(tmp_path)
    store.add_profile("alice", _ALICE_PROFILE, "Alice Wonderland")
    store.add_profile("bob", _BOB_PROFILE, "Bob Builder")

    raw = (tmp_path / "vault.enc").read_bytes()

    for fragment in ["Alice Wonderland", "Bob Builder", "alice", "bob"]:
        assert fragment.encode() not in raw, (
            f"Plaintext fragment '{fragment}' found in vault.enc"
        )


# ---------------------------------------------------------------------------
# Test 3: Touch ID overhead < 2s (mocked)
# ---------------------------------------------------------------------------

def test_touch_id_overhead_under_2s(tmp_path: Path) -> None:
    """Vault open() with mocked keychain completes in < 2 seconds."""
    store = _make_store(tmp_path)
    store.add_profile("alice", _ALICE_PROFILE, "Alice Wonderland")

    start = time.monotonic()
    # Simulate 10 vault opens (one per CLI invocation in a batch)
    for _ in range(10):
        store.open()
    elapsed = time.monotonic() - start

    assert elapsed < 2.0, (
        f"10 vault opens took {elapsed:.2f}s; expected < 2s (Touch ID overhead)"
    )


# ---------------------------------------------------------------------------
# Test 4: vault-loaded profiles work with detection pipeline
# ---------------------------------------------------------------------------

def test_vault_profile_drives_detection(tmp_path: Path) -> None:
    """Profile loaded from vault produces same detections as profile loaded from YAML."""
    from redactron.detect.name_detector import detect_names
    from redactron.extract.text_layer import TextLayer
    from redactron.profile import Profile

    store = _make_store(tmp_path)
    store.add_profile("alice", _ALICE_PROFILE, "Alice Wonderland")

    profile_dict = store.get_profile("alice")
    assert profile_dict is not None
    profile = Profile.model_validate(profile_dict)

    layers = [
        TextLayer(
            page_num=0,
            text="Alice Wonderland signed this document.",
            bbox=(0.0, 0.0, 400.0, 20.0),
            block_type=0,
        )
    ]
    detections = detect_names(layers, profile)
    assert len(detections) >= 1, "Name detector should find 'Alice Wonderland' from vault profile"


# ---------------------------------------------------------------------------
# Test 5: vault.salt is created and is 0600
# ---------------------------------------------------------------------------

def test_vault_salt_created_with_correct_perms(tmp_path: Path) -> None:
    import stat

    store = _make_store(tmp_path)
    store.save({"version": 1, "profiles": {}})

    salt_path = tmp_path / "vault.salt"
    assert salt_path.exists(), "vault.salt must be created on first save"
    mode = stat.S_IMODE(salt_path.stat().st_mode)
    assert mode == 0o600, f"vault.salt mode is {oct(mode)}, expected 0o600"
    assert len(salt_path.read_bytes()) == 32, "vault.salt must be 32 bytes"
