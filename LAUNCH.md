# Redactron v1.0

## Local-only PII redaction for PDFs

Redactron is a free, open-source CLI tool that redacts personally identifiable information from PDFs on your machine. No cloud. No subscriptions. No telemetry.

![Redactron demo](assets/demo.gif)

---

### The problem

Free online PDF redactors are ad-supported and many run analytics on the documents you upload. For medical records, legal documents, or anything covered by HIPAA, GDPR, or attorney-client privilege, that is a real concern. Adobe Acrobat uploads files to Adobe's servers. iLovePDF and SmallPDF are cloud services. You have no visibility into what happens to your files after upload.

Manual redaction in Acrobat is slow, error-prone, and does not scale. If you have a year of bank statements, credit card bills, and patient records to process, doing it by hand is not realistic.

---

### What Redactron does

You describe your client's PII once in a profile file: name, aliases, address, phone, email, SSN, account numbers. Then you point Redactron at a file or a folder and it handles the rest.

```bash
redactron run ./statements/ --client alice
```

Every PDF in the folder is processed. Scanned pages trigger OCR automatically. The output is re-scanned to verify nothing was missed. A batch report is written with the results.

Account numbers support partial redaction. Setting `preserve_last: 4` redacts the prefix and keeps the last 4 digits visible, which is the format most lenders and compliance teams require.

---

### Who it is for

**Accountants and bookkeepers** processing client financial records. Define one profile per client and run it against a full year of bank, brokerage, and credit card statements in a few minutes.

**Mortgage and loan professionals** assembling document packages. A single profile covers all statements from all institutions. Account numbers are redacted to the last 4 digits while transaction history stays intact.

**Medical and clinical staff** sharing patient records between providers or submitting to insurers. Name, date of birth, address, phone, insurance ID, and any custom fields are handled in one pass.

**Legal teams** producing documents in discovery. Every redaction is logged with the filename, page, detection type, and verification status.

**Anyone dealing with scanned documents.** Chase, Wells Fargo, and many other institutions produce statements where account numbers are rendered as images or in non-selectable text layers. Redactron's OCR fallback handles these without any extra flags or manual steps.

---

### Key features

- **Profile-driven.** Define PII once and redact any number of PDFs.
- **Encrypted vault.** AES-256-GCM encrypted profile store. Master key in macOS Keychain, gated by Touch ID.
- **Verification pass.** Re-scans the redacted output and reports any survivors.
- **OCR fallback.** Auto-triggers on image-only pages. No flag needed.
- **Partial redaction.** Keep the last N digits of account numbers visible.
- **Audit log.** SQLite record of every run with filename, detections, and verification status.
- **Batch mode.** One command processes an entire directory.
- **Zero telemetry.** No HTTP client in the codebase. Verified by packet capture.

---

### Getting started

```bash
pip install redactron
redactron init
redactron vault init

redactron profile template --output /tmp/alice.yaml
# fill in the YAML, then import (source file is wiped after import)
redactron profile add --client alice --from /tmp/alice.yaml

# single file
redactron run statement.pdf --client alice

# entire folder
redactron run ./statements/ --client alice
```

---

### What is inside

- **PyMuPDF** for PDF text extraction with character-level bounding boxes
- **Microsoft Presidio** for NLP-based entity detection
- **rapidfuzz** for fuzzy name matching
- **usaddress** for address parsing and normalization
- **pytesseract** for OCR on scanned pages
- **cryptography** for AES-256-GCM vault encryption
- **Pydantic v2** for profile schema validation
- **SQLite** for audit logging

---

### Platform support

- **macOS**: available now (Touch ID vault)
- **Linux**: v1.1 (keyring via libsecret)
- **Windows**: v1.1 (DPAPI)

---

### What is next

**v1.1** adds Linux and Windows support with platform-native credential storage.

**v1.2** adds on-device LLM assistance via Ollama or llama.cpp. A small local model will be able to draft your profile from a sample document, flag PII fields that do not match any profile entry across a batch, detect account numbers rendered as images or in non-standard formats, and correct OCR misreads in the context of known PII patterns. No API key. No data leaves the machine.

---

### License

AGPL-3.0. Redactron depends on PyMuPDF which is also AGPL-3.0. If you distribute Redactron as part of a proprietary product, the AGPL requires you to release your source.

---

### Links

- **GitHub**: https://github.com/tjndr/redactron
- **PyPI**: https://pypi.org/project/redactron/
- **Docs**: https://github.com/tjndr/redactron/tree/main/docs

Your files stay on your machine.
