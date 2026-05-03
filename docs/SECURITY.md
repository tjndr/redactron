# redactron — Security

## Threat model

| Actor | Capability | Mitigation |
|---|---|---|
| Offline attacker with disk access | Reads `vault.enc` from stolen laptop or cloud sync | AES-256-GCM ciphertext; useless without keychain master key |
| Accidental git commit | `vault.enc` pushed to repo | Opaque ciphertext; no plaintext PII |
| Cloud sync (iCloud, Dropbox) | `vault.enc` synced to cloud | Ciphertext only; `redactron init` warns on cloud-sync paths |
| Live malware on user's machine | Reads keychain via compromised process | Out of scope for v1; OS-level keychain protection applies |
| Kernel-level keychain compromise | Bypasses Touch ID | Out of scope; requires root/kernel exploit |
| Side-channel attacks | Timing, cache analysis | Out of scope for v1 |

## Crypto choices

### AES-256-GCM

- **Why GCM, not CBC:** GCM is authenticated encryption (AEAD). Any bit flip in the ciphertext raises `InvalidTag` before any plaintext is returned. CBC has no authentication tag — an attacker can flip bits and receive modified plaintext silently (padding oracle, bit-flip attacks).
- **Why not ChaCha20-Poly1305:** Deferred to v1.1 for cross-platform support. AES-GCM has hardware acceleration on all modern x86 and Apple Silicon.
- **Key size:** 256 bits (`secrets.token_bytes(32)`). NIST-approved for top-secret classification.
- **Nonce:** 96 bits (`os.urandom(12)`) generated fresh for every `save()` call. GCM nonce reuse with the same key is catastrophic (leaks keystream); fresh random nonces make reuse statistically impossible.

### Key management

- Master key: 32 bytes, generated once via `secrets.token_bytes(32)`.
- Stored exclusively in the macOS Keychain with `kSecAccessControlBiometryAny`.
- Never written to disk in plaintext. Never logged. Never in error messages.
- Access control: Touch ID required; passcode fallback after 5 failed Touch ID attempts.

### Access control flag: `kSecAccessControlBiometryAny`

- **Chosen over `kSecAccessControlBiometryCurrentSet`:** `CurrentSet` invalidates the keychain item when the user re-enrolls a fingerprint, locking them out of their vault. `BiometryAny` survives re-enrollment.
- **Chosen over `kSecAccessControlUserPresence`:** `UserPresence` allows passcode-only without ever requiring biometry, defeating the purpose of Touch ID protection.

### KDF (key rotation path)

If the master key ever needs to be rotated, Argon2id (t=2, m=64MB, p=1) can derive a new key from a passphrase. Per-vault salt (32 bytes) stored at `~/.redactron/vault.salt` (not encrypted; salts are public). This path is not used in normal operation — the keychain is the primary key store.

## File format

```
~/.redactron/vault.enc:
  Offset  Size  Field
  0       8     magic: b"REDV1\x00\x00\x00"
  8       12    nonce (random per encryption)
  20      16    AES-256-GCM authentication tag
  36      N     ciphertext (JSON payload)
```

The JSON payload is decrypted in-memory only and never written to disk.

## What this protects against

- Offline attacker with disk access (stolen laptop, cloud sync leak, accidental git commit)
- `vault.enc` is opaque ciphertext without the keychain master key

## What this does NOT protect against

- Live malware on the user's machine with keychain access
- Kernel-level keychain compromise
- Side-channel attacks (timing, cache)
- A user who exports their own keychain

## Platform support

| Platform | Status |
|---|---|
| macOS (darwin) | ✅ Supported in v1 |
| Linux | 🔜 Planned for v1.1 (libsecret/SecretService) |
| Windows | 🔜 Planned for v1.1 (DPAPI/Credential Manager) |

## Reporting security issues

Email: tejinder.singh@ieee.org

Please include:
- Description of the vulnerability
- Steps to reproduce
- Affected version(s)
- Potential impact

**Disclosure policy:** 90-day coordinated disclosure. We will acknowledge receipt within 48 hours and provide a fix timeline within 7 days. Public disclosure after 90 days or when a fix is released, whichever comes first.

PGP key available on request.
