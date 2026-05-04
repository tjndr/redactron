# redactron — Privacy

## Local-only guarantee

redactron processes all PDFs entirely on your machine. There are no network calls in the
redaction pipeline: not during detection, not during redaction, not during verification.
The codebase has no HTTP client dependency and no outbound socket calls.

You can verify this yourself:

```bash
# Run with network monitoring (macOS)
sudo tcpdump -i any -n 'host not 0.0.0.0' &
redactron run document.pdf
# No packets should appear
```

## What data is stored locally

### Audit log (`~/.redactron/audit.db`)

SQLite database recording each redaction run:

| Column | Value |
|---|---|
| `id` | Auto-increment integer |
| `original_filename` | Filename only (no path) |
| `output_filename` | Filename only |
| `profile_name` | Profile `name` field |
| `pages_processed` | Integer |
| `items_detected` | Integer |
| `items_redacted` | Integer |
| `verification_passed` | Boolean |
| `processed_at` | UTC timestamp |

The audit log does **not** store file paths, file contents, detected PII text, or any
personally identifiable information beyond what you explicitly put in your profile name.

### Encrypted vault (`~/.redactron/vault.enc`)

AES-256-GCM encrypted blob containing your client profiles. Decrypted in-memory only;
never written to disk in plaintext. See [SECURITY.md](SECURITY.md) for the full crypto
specification.

### Profile YAML (`~/.redactron/profile.yaml`)

Plain-text YAML containing your PII definitions. This file is **not** encrypted by default.
Protect it with filesystem permissions (`chmod 600`) or migrate to the vault:

```bash
redactron profile import ~/.redactron/profile.yaml --client default
```

## No telemetry

redactron collects no usage data, crash reports, or analytics. There is no opt-out because
there is nothing to opt out of.

## Cloud sync warning

If your home directory is synced to iCloud, Dropbox, or similar services:

- `vault.enc` is safe to sync. It is opaque ciphertext without the keychain master key.
- `profile.yaml` contains plaintext PII. Exclude it from sync or migrate to the vault.
- `audit.db` contains filenames and run metadata. Exclude it if you consider this sensitive.

Add to your sync exclusion list:
```
~/.redactron/profile.yaml
~/.redactron/audit.db
```

## AGPL-3.0 and PyMuPDF

redactron is licensed under AGPL-3.0. It depends on
[PyMuPDF](https://pymupdf.readthedocs.io/) (also AGPL-3.0).

**What this means for you:**

- **Personal use:** No restrictions. Use freely.
- **Internal business use:** No restrictions. You are not distributing the software.
- **Distribution as part of a proprietary product:** The AGPL requires you to release your
  complete source code (including modifications) under AGPL-3.0 when you distribute the
  combined work to users. This applies to SaaS if users interact with the software over a
  network.

If you need a commercial license for PyMuPDF that permits proprietary distribution, contact
[Artifex Software](https://artifex.com/licensing/).

## Compared to cloud redaction services

Free online redactors are usually ad-supported and many run analytics on the documents you
upload. For medical records, legal documents, or anything covered by HIPAA, GDPR, or
attorney-client privilege, that is a serious concern. Adobe Acrobat uploads files to
Adobe's servers. iLovePDF and SmallPDF are cloud services with freemium models. You have
no visibility into what happens to your files after upload.

redactron has no network calls in the redaction pipeline. The codebase has no HTTP client
dependency. You can verify this with a packet capture.

| Feature | redactron | Cloud services |
|---|---|---|
| Data leaves your machine | Never | Always |
| Works offline | Yes | No |
| Audit trail | Local SQLite | Varies |
| Profile-driven | Yes | Rarely |
| Verification | Built-in | Rarely |
| Cost | Free (AGPL) | Per-page fees |
| HIPAA/GLBA suitability | No BAA needed | Requires BAA |
