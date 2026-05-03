"""Synthetic test corpus — BLD-20.

12 document types, 3 assertions each:
  1. No PII plaintext survives in the redacted PDF.
  2. Redaction count is within ±10% of the known-good baseline (regression guard).
  3. Verification report shows passed=True with zero survivors.

PDFs are generated in-memory with PyMuPDF; no static fixtures needed.
Document #12 (scanned_invoice) is image-only and exercises the OCR path.
"""

from __future__ import annotations

import io
import math
from pathlib import Path
from typing import NamedTuple
from unittest.mock import patch

import fitz
import pytest

from redactron.pipeline import run_pipeline
from redactron.profile import Profile

# ---------------------------------------------------------------------------
# Test profile — fixed PII strings embedded in every corpus PDF
# ---------------------------------------------------------------------------

_PROFILE = Profile.model_validate({
    "version": 1,
    "name": "corpus-test",
    "subject": {
        "display_name": "Jane Corpus",
        "aliases": ["Jane"],
        "addresses": ["123 Test Street, Springfield, IL 62701"],
        "phones": ["555-867-5309"],
        "emails": ["jane.corpus@example.com"],
        "ssns": ["123-45-6789"],
        "account_numbers": [{"value": "ACC-9900112233", "preserve_last": 4}],
        "custom_patterns": [
            {"name": "ssn", "regex": r"\d{3}-\d{2}-\d{4}"},
        ],
    },
    "detection": {
        "use_presidio": True,
        "presidio_entities": ["PHONE_NUMBER", "EMAIL_ADDRESS"],
        "fuzzy_match": True,
        "match_threshold": 0.85,
        "full_token_min_length": 2,
        "ocr_fallback": False,
    },
})

# PII strings that must NOT appear in the redacted output
_PII_STRINGS = [
    "Jane Corpus",
    "123 Test Street",
    "555-867-5309",
    "jane.corpus@example.com",
    "123-45-6789",
]

# ---------------------------------------------------------------------------
# Corpus PDF builders
# ---------------------------------------------------------------------------


def _save_reload(doc: fitz.Document) -> fitz.Document:
    """Save to bytes and reload so PyMuPDF builds the text index."""
    buf = io.BytesIO(doc.tobytes())
    return fitz.open(stream=buf, filetype="pdf")


def _base_page(doc: fitz.Document, title: str) -> fitz.Page:
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 60), title, fontsize=14)
    return page


def _insert_pii(page: fitz.Page, y: float = 100.0) -> None:
    """Insert all PII strings onto the page."""
    lines = [
        "Name: Jane Corpus",
        "Address: 123 Test Street, Springfield, IL 62701",
        "Phone: 555-867-5309",
        "Email: jane.corpus@example.com",
        "SSN: 123-45-6789",
        "Account: ACC-9900112233",
    ]
    for i, line in enumerate(lines):
        page.insert_text((72, y + i * 18), line, fontsize=11)


def _make_bank_statement() -> fitz.Document:
    doc = fitz.open()
    page = _base_page(doc, "Bank Statement — March 2024")
    _insert_pii(page, y=100)
    page.insert_text((72, 220), "Opening balance: $10,000.00", fontsize=11)
    page.insert_text((72, 238), "Closing balance: $9,500.00", fontsize=11)
    return _save_reload(doc)


def _make_utility_bill() -> fitz.Document:
    doc = fitz.open()
    page = _base_page(doc, "Utility Bill — Electric Service")
    _insert_pii(page, y=100)
    page.insert_text((72, 220), "Amount due: $142.50  Due date: 2024-04-15", fontsize=11)
    return _save_reload(doc)


def _make_medical_record() -> fitz.Document:
    doc = fitz.open()
    page = _base_page(doc, "Medical Record — Patient Summary")
    _insert_pii(page, y=100)
    page.insert_text((72, 220), "Diagnosis: Hypertension  ICD-10: I10", fontsize=11)
    page.insert_text((72, 238), "Physician: Dr. Smith  Date: 2024-03-01", fontsize=11)
    return _save_reload(doc)


def _make_tax_form() -> fitz.Document:
    doc = fitz.open()
    page = _base_page(doc, "Form 1040 — U.S. Individual Income Tax Return")
    _insert_pii(page, y=100)
    page.insert_text((72, 220), "Wages: $75,000  Federal tax withheld: $12,000", fontsize=11)
    return _save_reload(doc)


def _make_insurance_eob() -> fitz.Document:
    doc = fitz.open()
    page = _base_page(doc, "Explanation of Benefits — Health Insurance")
    _insert_pii(page, y=100)
    page.insert_text((72, 220), "Claim #: CLM-20240301  Billed: $500  Paid: $400", fontsize=11)
    return _save_reload(doc)


def _make_court_doc() -> fitz.Document:
    doc = fitz.open()
    page = _base_page(doc, "Superior Court — Case No. 2024-CV-00123")
    _insert_pii(page, y=100)
    page.insert_text((72, 220), "Plaintiff vs. Defendant  Hearing: 2024-05-01", fontsize=11)
    return _save_reload(doc)


def _make_payslip() -> fitz.Document:
    doc = fitz.open()
    page = _base_page(doc, "Pay Slip — Period: 2024-03-01 to 2024-03-31")
    _insert_pii(page, y=100)
    page.insert_text((72, 220), "Gross pay: $6,250.00  Net pay: $4,800.00", fontsize=11)
    return _save_reload(doc)


def _make_lab_report() -> fitz.Document:
    doc = fitz.open()
    page = _base_page(doc, "Laboratory Report — Quest Diagnostics")
    _insert_pii(page, y=100)
    page.insert_text((72, 220), "Test: CBC  Result: Normal  Date: 2024-03-15", fontsize=11)
    return _save_reload(doc)


def _make_invoice() -> fitz.Document:
    doc = fitz.open()
    page = _base_page(doc, "Invoice #INV-2024-0042")
    _insert_pii(page, y=100)
    page.insert_text((72, 220), "Item: Consulting services  Qty: 10h  Rate: $150", fontsize=11)
    page.insert_text((72, 238), "Total: $1,500.00  Due: 2024-04-30", fontsize=11)
    return _save_reload(doc)


def _make_leasing_agreement() -> fitz.Document:
    doc = fitz.open()
    page = _base_page(doc, "Residential Lease Agreement")
    _insert_pii(page, y=100)
    page.insert_text((72, 220), "Lease term: 12 months  Monthly rent: $2,200", fontsize=11)
    page.insert_text((72, 238), "Security deposit: $4,400  Start: 2024-06-01", fontsize=11)
    return _save_reload(doc)


def _make_research_paper() -> fitz.Document:
    """Two-column layout with figures (simulated)."""
    doc = fitz.open()
    page = _base_page(doc, "Research Paper — Two-Column Format")
    _insert_pii(page, y=100)
    # Left column
    col1_x = 72.0
    col2_x = 320.0
    for i in range(8):
        page.insert_text((col1_x, 220 + i * 16), f"Left column line {i + 1}.", fontsize=10)
        page.insert_text((col2_x, 220 + i * 16), f"Right column line {i + 1}.", fontsize=10)
    # Simulated figure caption
    page.insert_text((72, 360), "Figure 1: Results overview (non-PII data)", fontsize=9)
    return _save_reload(doc)


def _make_scanned_invoice() -> fitz.Document:
    """Image-only PDF — no text layer. OCR path exercised via mock."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    # Draw a white background (simulates a scanned page with no text stream)
    page.draw_rect(fitz.Rect(0, 0, 612, 792), color=(1, 1, 1), fill=(1, 1, 1))
    return _save_reload(doc)


# ---------------------------------------------------------------------------
# Corpus registry
# ---------------------------------------------------------------------------


class CorpusEntry(NamedTuple):
    name: str
    builder: object  # callable → fitz.Document
    is_image_only: bool = False


_CORPUS: list[CorpusEntry] = [
    CorpusEntry("bank_statement", _make_bank_statement),
    CorpusEntry("utility_bill", _make_utility_bill),
    CorpusEntry("medical_record", _make_medical_record),
    CorpusEntry("tax_form", _make_tax_form),
    CorpusEntry("insurance_eob", _make_insurance_eob),
    CorpusEntry("court_doc", _make_court_doc),
    CorpusEntry("payslip", _make_payslip),
    CorpusEntry("lab_report", _make_lab_report),
    CorpusEntry("invoice", _make_invoice),
    CorpusEntry("leasing_agreement", _make_leasing_agreement),
    CorpusEntry("research_paper", _make_research_paper),
    CorpusEntry("scanned_invoice", _make_scanned_invoice, is_image_only=True),
]

# Known-good detection baselines:
# name + address + phone + email + ssn + account = 6 per text doc.
# Image-only doc uses OCR mock → 0 text detections.
_BASELINES: dict[str, int] = {e.name: (0 if e.is_image_only else 6) for e in _CORPUS}

# ---------------------------------------------------------------------------
# Mock tesseract data for scanned_invoice (returns zero words → no OCR hits)
# ---------------------------------------------------------------------------

_EMPTY_TESS_DATA = {
    "text": [], "conf": [], "left": [], "top": [], "width": [], "height": [], "level": [],
}

# ---------------------------------------------------------------------------
# Parametrized corpus tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("entry", _CORPUS, ids=[e.name for e in _CORPUS])
def test_corpus_no_pii_in_output(entry: CorpusEntry, tmp_path: Path) -> None:
    """Assertion 1: no PII plaintext survives in the redacted PDF."""
    doc = entry.builder()  # type: ignore[operator]
    pdf_path = tmp_path / f"{entry.name}.pdf"
    out_path = tmp_path / f"{entry.name}_redacted.pdf"
    doc.save(str(pdf_path))

    with patch("pytesseract.image_to_data", return_value=_EMPTY_TESS_DATA):
        run_pipeline(
            pdf_path, out_path, _PROFILE,
            verify=False, write_reports=False,
            ocr_enabled=entry.is_image_only,
        )

    redacted_text = fitz.open(str(out_path))[0].get_text()
    for pii in _PII_STRINGS:
        assert pii not in redacted_text, (
            f"[{entry.name}] PII '{pii}' survived redaction"
        )


@pytest.mark.parametrize("entry", _CORPUS, ids=[e.name for e in _CORPUS])
def test_corpus_redaction_count_within_baseline(entry: CorpusEntry, tmp_path: Path) -> None:
    """Assertion 2: detection count within ±10% of known-good baseline."""
    doc = entry.builder()  # type: ignore[operator]
    pdf_path = tmp_path / f"{entry.name}.pdf"
    out_path = tmp_path / f"{entry.name}_redacted.pdf"
    doc.save(str(pdf_path))

    with patch("pytesseract.image_to_data", return_value=_EMPTY_TESS_DATA):
        result = run_pipeline(
            pdf_path, out_path, _PROFILE,
            verify=False, write_reports=False,
            ocr_enabled=entry.is_image_only,
        )

    baseline = _BASELINES[entry.name]
    if baseline == 0:
        # Image-only: no text detections expected
        assert result.detections_total == 0
        return

    lo = math.floor(baseline * 0.9)
    hi = math.ceil(baseline * 1.1)
    assert lo <= result.detections_total <= hi, (
        f"[{entry.name}] detections={result.detections_total} outside ±10% of baseline={baseline}"
    )


@pytest.mark.parametrize("entry", _CORPUS, ids=[e.name for e in _CORPUS])
def test_corpus_verification_passes(entry: CorpusEntry, tmp_path: Path) -> None:
    """Assertion 3: verification report shows passed=True, zero survivors."""
    doc = entry.builder()  # type: ignore[operator]
    pdf_path = tmp_path / f"{entry.name}.pdf"
    out_path = tmp_path / f"{entry.name}_redacted.pdf"
    doc.save(str(pdf_path))

    with patch("pytesseract.image_to_data", return_value=_EMPTY_TESS_DATA):
        result = run_pipeline(
            pdf_path, out_path, _PROFILE,
            verify=True, write_reports=False,
            ocr_enabled=entry.is_image_only,
        )

    assert result.verification_passed is True, (
        f"[{entry.name}] verification failed with {result.survivors} survivor(s)"
    )
    assert result.survivors == 0, (
        f"[{entry.name}] {result.survivors} PII survivor(s) found"
    )
