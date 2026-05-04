# Redactron v1.0 Launch Post

## Redactron: Local-only PII redaction for PDFs

**Today we're shipping Redactron v1.0** — a free, open-source CLI tool that redacts personally identifiable information (PII) from PDFs on your machine. No cloud. No subscriptions. No telemetry.

### The Problem

Free online PDF redactors are ad-supported and many run analytics on the documents you upload. For medical records, legal documents, or anything covered by HIPAA, GDPR, or attorney-client privilege, that's a serious concern. Adobe Acrobat uploads files to Adobe's servers. iLovePDF and SmallPDF are cloud services with freemium models. You have no visibility into what happens to your files after upload.

### The Solution

Redactron runs entirely on your machine. The codebase has no HTTP client dependency and no outbound socket calls. You can verify this with a packet capture while running a redaction.

**Key features:**

- **Profile-driven.** Define your PII once (names, aliases, addresses, phones, emails, SSNs, account numbers, custom regex) and redact any number of PDFs.
- **Encrypted vault.** AES-256-GCM encrypted multi-client profile store. Master key in macOS Keychain, gated by Touch ID.
- **Verification.** Re-scans the redacted output and reports any PII survivors.
- **OCR fallback.** Auto-triggers on image-only pages via pytesseract. No flag needed.
- **Audit log.** SQLite record of every run (filename, detections, verification status).
- **Batch mode.** `redactron run ./docs/` redacts an entire directory. Outputs go to `redacted/` subdir.
- **AGPL-3.0.** Source is open for inspection. No black-box model deciding what to redact.

### Getting Started

```bash
pip install redactron
redactron init
redactron vault init

# Get the profile template
redactron profile template --output /tmp/me.yaml
# edit /tmp/me.yaml with your name, addresses, account numbers, etc.
redactron profile add --client me --from /tmp/me.yaml

# Redact a single file
redactron run document.pdf --client me

# Redact multiple files in a folder
redactron run ./documents/ --client me
```

### What's Inside

- **PyMuPDF** for PDF text extraction with character-level bounding boxes
- **Microsoft Presidio** for NLP-based entity detection
- **rapidfuzz** for fuzzy name matching
- **usaddress** for address parsing and normalization
- **pytesseract** for OCR fallback on scanned documents
- **cryptography** for AES-256-GCM vault encryption
- **Pydantic v2** for profile schema validation
- **SQLite** for audit logging

### Platform Support

- **macOS**: First-class support (Touch ID vault)
- **Linux**: Planned for v1.1 (keyring via libsecret)
- **Windows**: Planned for v1.1 (DPAPI)

### What's Next

**v1.1** will add Linux and Windows support with platform-native credential storage.

**v1.5** will ship a Gradio web UI with drag-drop folder upload, real-time redaction, visual diff overlay, and profile editing via browser.

### License

AGPL-3.0. Redactron depends on PyMuPDF which is also AGPL-3.0. If you distribute redactron as part of a proprietary product, the AGPL requires you to release your source.

### Links

- **GitHub**: https://github.com/tjndr/redactron
- **PyPI**: https://pypi.org/project/redactron/
- **Docs**: https://github.com/tjndr/redactron/tree/main/docs
- **License**: AGPL-3.0

---

**Try it today.** Your files stay on your machine.
