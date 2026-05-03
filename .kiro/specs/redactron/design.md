# Redactron — Design

## Architecture

Redactron is a local-only CLI pipeline. Each stage is a pure module with no side effects
except the final write and audit log.

```
PDF input
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│  extract/                                                   │
│  text_layer.py  ──► List[TextLayer]  (page, text, bbox)     │
│  ocr.py         ──► List[TextLayer]  (OCR fallback)         │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│  detect/                                                    │
│  presidio_detector.py  ──► List[Detection]                  │
│  name_detector.py      ──► List[Detection]  (fuzzy)         │
│  address_detector.py   ──► List[Detection]  (normalized)    │
│  account_detector.py   ──► List[Detection]  (regex)         │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│  redact/                                                    │
│  engine.py   ──► redacted fitz.Document                     │
│  partial.py  ──► partial redaction (last-N preserve)        │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│  verify/                                                    │
│  verifier.py  ──► VerificationResult (passed, survivors)    │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│  audit/                                                     │
│  log.py  ──► SQLite write (documents + subjects tables)     │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│  report/                                                    │
│  markdown.py  ──► .report.md + .report.json                 │
└─────────────────────────────────────────────────────────────┘
```

## Module Boundaries

| Module | Responsibility | Inputs | Outputs |
|--------|---------------|--------|---------|
| `extract/text_layer.py` | Read-only PDF parsing | `fitz.Document` | `List[TextLayer]` |
| `extract/ocr.py` | OCR fallback for image pages | `fitz.Page` | `List[TextLayer]` |
| `detect/presidio_detector.py` | Presidio NER detection | `List[TextLayer]`, `Profile` | `List[Detection]` |
| `detect/name_detector.py` | Fuzzy name matching | `List[TextLayer]`, `Profile` | `List[Detection]` |
| `detect/address_detector.py` | Address normalization + match | `List[TextLayer]`, `Profile` | `List[Detection]` |
| `detect/account_detector.py` | Regex pattern matching | `List[TextLayer]`, `Profile` | `List[Detection]` |
| `redact/engine.py` | Apply redaction annotations | `fitz.Document`, `List[Detection]` | `fitz.Document` |
| `redact/partial.py` | Partial redaction (last-N) | `fitz.Document`, `Detection` | `fitz.Document` |
| `verify/verifier.py` | Post-redaction re-detection | `fitz.Document`, `Profile` | `VerificationResult` |
| `audit/log.py` | SQLite I/O only | `DocumentRecord` | None |
| `report/markdown.py` | Report generation | `DocumentRecord`, `VerificationResult` | `str` (markdown) |
| `cli.py` | Orchestration only | CLI args | Exit code |

## Key Data Structures

```python
@dataclass
class TextLayer:
    page_num: int
    text: str
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1
    block_type: int  # fitz block type

@dataclass
class Detection:
    text: str
    entity_type: str
    start: int
    end: int
    score: float
    page_num: int
    bbox: tuple[float, float, float, float]
    preserve_last: int = 0  # for partial redaction

@dataclass
class VerificationResult:
    passed: bool
    survivors: list[Detection]
    duration_ms: int
```

## Repo Layout

```
redactron/
├── .github/workflows/{ci,release}.yml
├── .kiro/
│   ├── settings/mcp.json
│   ├── steering/{product,tech,conventions}.md
│   ├── specs/redactron/{requirements,design,tasks}.md
│   └── hooks/{on-task-start,on-tests-pass,on-pr-merge}.yml
├── .redactron/credits.db
├── src/redactron/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── errors.py
│   ├── profile.py
│   ├── detect/{presidio_detector,address_detector,account_detector,name_detector}.py
│   ├── extract/{text_layer,ocr}.py
│   ├── redact/{engine,partial}.py
│   ├── verify/verifier.py
│   ├── audit/log.py
│   ├── report/markdown.py
│   ├── vault/
│   │   ├── __init__.py
│   │   ├── store.py      # VaultStore, VaultEntry, open/seal
│   │   ├── keychain.py   # KeychainBackend ABC + platform backends
│   │   └── migrate.py    # migrate_profile(), secure_wipe()
│   └── web/app.py  (M5 only)
├── tests/
│   ├── fixtures/  (10 synthetic PDFs)
│   ├── test_detect.py
│   ├── test_redact.py
│   ├── test_verify.py
│   ├── test_vault.py
│   ├── test_keychain.py
│   ├── test_migration.py
│   └── test_e2e.py
├── docs/
│   ├── PROFILE.md
│   ├── PRIVACY.md
│   └── SECURITY.md       # M3.5.6
├── pyproject.toml
├── LICENSE  (AGPL-3.0)
├── README.md
└── CHANGELOG.md
```

## Vault and keychain integration

### File format

| File | Path | Description |
|------|------|-------------|
| `vault.enc` | `~/.redactron/vault.enc` | AES-256-GCM ciphertext of all client profiles |
| `vault.salt` | `~/.redactron/vault.salt` | Per-vault random salt (plaintext, 32 bytes hex) |

The vault file is a single encrypted blob. The encryption key is derived from the master
secret stored in the OS keychain using Argon2id (or HKDF). The salt is stored separately
so the vault file itself contains no key material.

### Key management abstraction

```python
from abc import ABC, abstractmethod

class KeychainBackend(ABC):
    @abstractmethod
    def get_master_key(self) -> bytes: ...

    @abstractmethod
    def set_master_key(self, key: bytes) -> None: ...
```

`get_keychain_backend() → KeychainBackend` auto-detects platform via `sys.platform`.

### OS keychain backends

| Platform | Backend | Status |
|----------|---------|--------|
| macOS | `MacOSKeychainBackend` — `keyring` + `kSecAccessControlBiometryAny` | v1 |
| Linux | `LinuxKeychainBackend` — `libsecret` via `keyring` | v1.1 (stub raises `NotImplementedError`) |
| Windows | `WindowsKeychainBackend` — DPAPI via `keyring` | v1.1 (stub raises `NotImplementedError`) |

### Touch ID flow on macOS

Every call to `get_master_key()` triggers a Touch ID prompt via
`kSecAccessControlBiometryAny`. There is no in-process caching of the master key.
The sequence for `redactron run doc.pdf --client acme`:

```
CLI → VaultStore.open(backend)
        → MacOSKeychainBackend.get_master_key()   ← Touch ID prompt
        → derive_key(master_key, salt)
        → AES-256-GCM decrypt vault.enc
        → extract client_id="acme" row
        → deserialize Profile
      → existing extract → detect → redact → verify pipeline
```

### Profile entry schema

```python
@dataclass
class VaultEntry:
    client_id: str          # slug, primary key
    display_name: str
    created_at: datetime
    updated_at: datetime
    profile_json: str       # full Profile struct serialized as JSON
    notes: str              # encrypted alongside profile_json
```

### Backwards compatibility

Legacy `~/.redactron/profile.yaml` continues to work in v1 with a deprecation warning:

```
DeprecationWarning: profile.yaml is deprecated; migrate with 'redactron profile import'
```

When `--client` is not given and no vault exists, the legacy profile is loaded. When a
vault exists, `--client default` is used. Migration path: `redactron profile import
old.yaml --client default`.

### New typed exceptions

- `VaultError` — any crypto failure (wrong key, corrupt ciphertext, missing salt)
- `KeychainError` — OS keychain unavailable or biometric auth failed

Both live in `redactron.errors`.

### BLD-29 Vault file format (implemented)

Binary layout of `~/.redactron/vault.enc`:

```
Offset  Size  Field
0       8     magic: b"REDV1\x00\x00\x00"  (version tag)
8       12    nonce: os.urandom(12) per encryption
20      16    tag:   AES-256-GCM authentication tag
36      N     ciphertext: AES-256-GCM encrypted JSON payload
Total = 36 + N bytes
```

Crypto choices:
- **AES-256-GCM** (not CBC/ECB): authenticated encryption — any tampering raises `InvalidTag`
- **96-bit nonce** per encryption: GCM standard; nonce reuse with same key is catastrophic, so a fresh `os.urandom(12)` is generated for every `save()` call
- **`secrets.token_bytes(32)`** for master key: CSPRNG, never written to disk
- **Argon2id** (t=2, m=64MB, p=1) available for KDF if key rotation needed; per-vault salt at `vault.salt`

`KeychainBackend` Protocol (2 methods):
- `get_or_create_master_key(vault_id: str) -> bytes`
- `delete_master_key(vault_id: str) -> None`

Atomic write: `vault.enc.tmp` → fsync → rename. File permissions enforced at 0600 on every save; `SecurityError` raised if looser on load.

## Performance Targets

| Scenario | Target |
|----------|--------|
| 10-page text PDF | < 3s end-to-end including verification |
| 10-page image PDF (OCR) | < 30s |
| Peak memory per document | < 500 MB |

## Error Handling

All typed exceptions live in `redactron.errors`:
- `ProfileValidationError` — bad profile.yaml
- `ExtractionError` — PDF unreadable/encrypted
- `RedactionError` — redaction failed
- `VerificationError` — survivors found post-redaction

CLI catches all and prints user-friendly messages; `--debug` shows full stack trace.

## OCR Fallback (BLD-19)

### Trigger
Per-page auto-detection: if `len(page.get_text().strip()) < 50`, the page is
treated as image-only and passed to Tesseract.  Mixed PDFs (some text pages,
some image pages) are handled correctly — only image pages are OCR'd.

### Coordinate conversion
Tesseract returns bounding boxes in **pixel space** at the render DPI.
PDF coordinates are in **points** (1 pt = 1/72 inch).  The conversion is:

```
scale = 72 / dpi          # e.g. 72/300 = 0.24
pdf_x = pixel_x * scale
```

Omitting this scale factor would place redaction boxes ~4.17× too large at
300 DPI (the default), causing severe over-redaction.

### Confidence threshold
Words with Tesseract confidence < 60 are skipped and counted in
`OcrPageResult.low_conf_count`.  A warning is logged per page.

### Sanity guards (reused thresholds)
Same constants as `redact/engine.py`:
- Reject word bbox covering > 30% of page area.
- Reject word bbox taller than 4× median word height on that page.

### Redaction strategy
Image pages have no text content stream, so `page.add_redact_annot` has
nothing to remove.  Instead, `paint_ocr_redactions` uses
`page.draw_rect(rect, color=(0,0,0), fill=(0,0,0))` to paint black rectangles
directly into the page content stream.

### CLI flags
`--ocr` / `--no-ocr` on the `run` command.  Default: `--no-ocr` (auto-detect
still raises `NoTextLayerError` for fully image-only PDFs without the flag).

