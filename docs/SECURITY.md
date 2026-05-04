# redactron — Security

## Threat model

| Actor | Capability | Mitigation |
|---|---|---|
| Offline attacker with disk access | Reads `vault.enc` from stolen laptop or cloud sync | AES-256-GCM ciphertext; useless without keychain master key |
| Accidental git commit | `vault.enc` pushed to repo | Opaque ciphertext; no plaintext PII |
| Cloud sync (iCloud, Dropbox) | `vault.enc` synced to cloud | Ciphertext only; `redactron init` warns on cloud-sync paths |
| Physical access to unlocked machine | Reads vault without user present | Touch ID required via LocalAuthentication before every vault access |
| Live malware on user's machine | Reads keychain directly (bypassing redactron) | Soft enforcement only. See limitations below. |
| Kernel-level compromise | Bypasses all user-space controls | Out of scope |

## Crypto choices

### AES-256-GCM

- **Why GCM, not CBC:** GCM is authenticated encryption (AEAD). Any bit flip in the ciphertext raises `InvalidTag` before any plaintext is returned. CBC has no authentication tag; an attacker can flip bits and receive modified plaintext silently.
- **Why not ChaCha20-Poly1305:** Deferred to v1.1 for cross-platform support. AES-GCM has hardware acceleration on all modern x86 and Apple Silicon.
- **Key size:** 256 bits (`secrets.token_bytes(32)`). NIST-approved for top-secret classification.
- **Nonce:** 96 bits (`os.urandom(12)`) generated fresh for every `save()` call. GCM nonce reuse with the same key is catastrophic; fresh random nonces make reuse statistically impossible.

### Key management

- Master key: 32 bytes, generated once via `secrets.token_bytes(32)`.
- Stored in the macOS login keychain via the `keyring` library.
- Touch ID required before every vault access via `LAContext.evaluatePolicy` (LocalAuthentication framework).
- Never written to disk in plaintext. Never logged. Never in error messages.

### Touch ID implementation

redactron uses `LAContext.evaluatePolicy(LAPolicyDeviceOwnerAuthenticationWithBiometrics)` from the LocalAuthentication framework before every vault access. This is **soft enforcement**:

- The Touch ID prompt fires; if cancelled or failed, redactron refuses to proceed.
- The master key is stored in the login keychain (standard ACL, not `kSecAttrAccessControl`).
- This works for unsigned Python processes. No Apple Developer account or code signing required.
- A determined attacker with shell access to your unlocked machine could read the keychain directly, bypassing redactron's Touch ID gate.

**Why not `kSecAttrAccessControl` (hardware-backed ACL)?**
`SecItemAdd` with `kSecAttrAccessControl` requires the `keychain-access-groups` entitlement, which is only available to code-signed apps distributed through Apple's channels. An unsigned `pip install` package cannot use it. The LocalAuthentication soft-gate provides equivalent UX (Touch ID prompt on every access) with the same threat model as tools like `sudo-touchid`.

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
- Physical access to unlocked machine (Touch ID required before vault access)
- `vault.enc` is opaque ciphertext without the keychain master key

## What this does NOT protect against

- Live malware with direct keychain access (bypasses redactron's Touch ID gate)
- Kernel-level compromise
- Side-channel attacks (timing, cache)
- A user who reads their own keychain directly

## Platform support

| Platform | Status |
|---|---|
| macOS (darwin) | Supported in v1. Touch ID via LocalAuthentication. |
| Linux | Planned for v1.1 (libsecret/SecretService) |
| Windows | Planned for v1.1 (DPAPI/Credential Manager) |

## Reporting security issues

Email: tejinder.singh@ieee.org

Please include:
- Description of the vulnerability
- Steps to reproduce
- Affected version(s)
- Potential impact

**Disclosure policy:** 90-day coordinated disclosure. We will acknowledge receipt within 48 hours and provide a fix timeline within 7 days. Public disclosure after 90 days or when a fix is released, whichever comes first.

PGP key available on request.
