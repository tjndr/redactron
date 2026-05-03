"""Tests for the post-redaction verifier (BLD-13 / M3.1).

Uses synthetic in-memory PDFs to avoid fixture file dependencies.
"""

from __future__ import annotations

import io

import fitz
import pytest

from redactron.detect.presidio_detector import Detection
from redactron.errors import VerificationError
from redactron.profile import DetectionConfig, Profile, Subject
from redactron.verify.verifier import VerificationResult, _is_preserved_suffix, verify_redaction

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pdf(text: str) -> fitz.Document:
    """Create a single-page in-memory PDF with the given text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), text, fontsize=12)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return fitz.open(stream=buf.read(), filetype="pdf")


def _make_profile(
    display_name: str = "Alice Sample",
    aliases: list[str] | None = None,
) -> Profile:
    return Profile(
        subject=Subject(
            display_name=display_name,
            aliases=aliases or [],
        ),
        detection=DetectionConfig(
            fuzzy_match=True,
            match_threshold=0.85,
        ),
    )


def _make_detection(text: str, page_num: int = 0, preserve_last: int = 0) -> Detection:
    return Detection(
        text=text,
        entity_type="PERSON",
        score=1.0,
        page_num=page_num,
        bbox=(0.0, 0.0, 100.0, 20.0),
        preserve_last=preserve_last,
    )


# ---------------------------------------------------------------------------
# VerificationResult dataclass
# ---------------------------------------------------------------------------

class TestVerificationResult:
    def test_passed_true_no_survivors(self) -> None:
        vr = VerificationResult(passed=True)
        assert vr.passed is True
        assert vr.survivors == []
        assert vr.duration_ms == 0

    def test_passed_false_with_survivors(self) -> None:
        det = _make_detection("Alice Sample")
        vr = VerificationResult(passed=False, survivors=[det], duration_ms=42)
        assert vr.passed is False
        assert len(vr.survivors) == 1
        assert vr.duration_ms == 42


# ---------------------------------------------------------------------------
# _is_preserved_suffix
# ---------------------------------------------------------------------------

class TestIsPreservedSuffix:
    def test_matching_suffix(self) -> None:
        det = _make_detection("1234567890123456", preserve_last=4)
        assert _is_preserved_suffix("3456", [det]) is True

    def test_non_matching_suffix(self) -> None:
        det = _make_detection("1234567890123456", preserve_last=4)
        assert _is_preserved_suffix("1234", [det]) is False

    def test_no_preserve_last(self) -> None:
        det = _make_detection("1234567890123456", preserve_last=0)
        assert _is_preserved_suffix("3456", [det]) is False

    def test_hyphenated_account_suffix(self) -> None:
        det = _make_detection("1234-5678-9012-3456", preserve_last=4)
        assert _is_preserved_suffix("3456", [det]) is True

    def test_empty_survivor(self) -> None:
        det = _make_detection("1234567890123456", preserve_last=4)
        assert _is_preserved_suffix("", [det]) is False

    def test_empty_original_detections(self) -> None:
        assert _is_preserved_suffix("3456", []) is False


# ---------------------------------------------------------------------------
# verify_redaction — clean document (no PII)
# ---------------------------------------------------------------------------

class TestVerifyRedactionClean:
    def test_clean_doc_passes(self) -> None:
        doc = _make_pdf("This document contains no personal information.")
        profile = _make_profile()
        result = verify_redaction(doc, profile)
        assert isinstance(result, VerificationResult)
        assert result.passed is True
        assert result.survivors == []
        assert result.duration_ms >= 0

    def test_clean_doc_no_raise(self) -> None:
        doc = _make_pdf("Invoice #12345 dated 2024-01-01.")
        profile = _make_profile()
        result = verify_redaction(doc, profile, raise_on_survivors=True)
        assert result.passed is True


# ---------------------------------------------------------------------------
# verify_redaction — document with surviving PII
# ---------------------------------------------------------------------------

class TestVerifyRedactionSurvivors:
    def test_name_survivor_detected(self) -> None:
        doc = _make_pdf("Prepared by Alice Sample for review.")
        profile = _make_profile(display_name="Alice Sample")
        result = verify_redaction(doc, profile)
        assert result.passed is False
        assert len(result.survivors) >= 1
        survivor_texts = [s.text for s in result.survivors]
        assert any("Alice" in t or "Sample" in t for t in survivor_texts)

    def test_raise_on_survivors(self) -> None:
        doc = _make_pdf("Contact: Alice Sample, alice@example.com")
        profile = _make_profile(display_name="Alice Sample")
        with pytest.raises(VerificationError, match="survived redaction"):
            verify_redaction(doc, profile, raise_on_survivors=True)

    def test_duration_ms_populated(self) -> None:
        doc = _make_pdf("Alice Sample")
        profile = _make_profile(display_name="Alice Sample")
        result = verify_redaction(doc, profile)
        assert result.duration_ms >= 0


# ---------------------------------------------------------------------------
# verify_redaction — partial redaction survivor filtering
# ---------------------------------------------------------------------------

class TestVerifyRedactionPartialFilter:
    def test_preserved_suffix_not_counted_as_survivor(self) -> None:
        """Last-4 digits of an account number should not be a survivor."""
        # Simulate a doc where only the last 4 digits remain after redaction
        doc = _make_pdf("Account ending in 3456")
        profile = _make_profile()
        original = [_make_detection("1234567890123456", preserve_last=4)]
        # The text "3456" alone should not trigger a name/address detection,
        # and even if it did, the filter should remove it.
        result = verify_redaction(doc, profile, original_detections=original)
        # No name/address detections expected for "Account ending in 3456"
        assert result.passed is True


# ---------------------------------------------------------------------------
# verify_redaction — empty document
# ---------------------------------------------------------------------------

class TestVerifyRedactionEmpty:
    def test_empty_doc_passes(self) -> None:
        doc = fitz.open()
        doc.new_page()
        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        empty_doc = fitz.open(stream=buf.read(), filetype="pdf")
        profile = _make_profile()
        result = verify_redaction(empty_doc, profile)
        assert result.passed is True
        assert result.survivors == []
