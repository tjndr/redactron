"""Tests for src/redactron/redact/partial.py (BLD-10)."""

from __future__ import annotations

import fitz
import pytest as _pytest

from redactron.profile import AccountNumber, DetectionConfig, Profile, Subject
from redactron.redact.partial import (
    _digits_only,
    _find_account_in_text,
    detect_account_numbers,
    mask_account_number,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _profile(accounts: list[AccountNumber], threshold: float = 0.85) -> Profile:
    return Profile(
        subject=Subject(display_name="Test User", account_numbers=accounts),
        detection=DetectionConfig(match_threshold=threshold),
    )


def _make_pdf(text: str) -> fitz.Document:
    """Create a minimal single-page PDF with the given text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), text, fontsize=12)
    # Re-open from bytes so rawdict is available
    buf = doc.tobytes()
    return fitz.open(stream=buf, filetype="pdf")


# ---------------------------------------------------------------------------
# Unit tests: _digits_only
# ---------------------------------------------------------------------------

def test_digits_only_strips_separators() -> None:
    assert _digits_only("1234-5678-9012-3456") == "1234567890123456"


def test_digits_only_plain() -> None:
    assert _digits_only("1234567890123456") == "1234567890123456"


def test_digits_only_empty() -> None:
    assert _digits_only("") == ""


# ---------------------------------------------------------------------------
# Unit tests: mask_account_number
# ---------------------------------------------------------------------------

def test_mask_hyphenated_last4() -> None:
    """1234-5678-9012-3456 -> XXXX-XXXX-XXXX-3456."""
    assert mask_account_number("1234-5678-9012-3456", 4) == "XXXX-XXXX-XXXX-3456"


def test_mask_plain_last4() -> None:
    """Plain 16-digit number masked to last 4."""
    assert mask_account_number("1234567890123456", 4) == "XXXXXXXXXXXX3456"


def test_mask_preserve_zero_redacts_all() -> None:
    """preserve_last=0 redacts all digits."""
    assert mask_account_number("1234-5678", 0) == "XXXX-XXXX"


def test_mask_preserve_more_than_length() -> None:
    """preserve_last >= len(digits) keeps all digits."""
    assert mask_account_number("1234", 6) == "1234"


def test_mask_preserves_separators() -> None:
    """Separators stay in their original positions."""
    result = mask_account_number("12 34 56 78", 4)
    assert result == "XX XX 56 78"


# ---------------------------------------------------------------------------
# Unit tests: _find_account_in_text
# ---------------------------------------------------------------------------

def test_find_exact_match() -> None:
    acct = AccountNumber(value="1234567890123456", preserve_last=4)
    matches = _find_account_in_text("1234567890123456", acct)
    assert len(matches) == 1
    assert matches[0] == (0, 16)


def test_find_hyphenated_in_text() -> None:
    acct = AccountNumber(value="1234567890123456", preserve_last=4)
    text = "Account: 1234-5678-9012-3456 end"
    matches = _find_account_in_text(text, acct)
    assert len(matches) == 1
    start, end = matches[0]
    assert text[start:end] == "1234-5678-9012-3456"


def test_find_account_with_no_digits_returns_empty() -> None:
    """Account value with no digits returns no matches (line 41 branch)."""
    acct = AccountNumber(value="no-digits", preserve_last=1)
    assert _find_account_in_text("some text 1234", acct) == []


def test_find_no_match() -> None:
    acct = AccountNumber(value="9999999999999999", preserve_last=4)
    assert _find_account_in_text("1234-5678-9012-3456", acct) == []


# ---------------------------------------------------------------------------
# Integration tests: detect_account_numbers with real PDF
# ---------------------------------------------------------------------------

def test_detect_finds_account_in_pdf() -> None:
    """Account number is detected in a synthetic PDF."""
    doc = _make_pdf("Account: 1234-5678-9012-3456")
    profile = _profile([AccountNumber(value="1234567890123456", preserve_last=4)])
    detections = detect_account_numbers(doc, profile)
    assert len(detections) >= 1
    assert detections[0].entity_type == "ACCOUNT_NUMBER"
    assert detections[0].preserve_last == 4


def test_detect_no_accounts_in_profile_returns_empty() -> None:
    """Profile with no account numbers returns empty list."""
    doc = _make_pdf("1234-5678-9012-3456")
    assert detect_account_numbers(doc, _profile([])) == []


def test_detect_score_is_1() -> None:
    """Account number detections have score=1.0 (exact match)."""
    doc = _make_pdf("1234-5678-9012-3456")
    profile = _profile([AccountNumber(value="1234567890123456", preserve_last=4)])
    detections = detect_account_numbers(doc, profile)
    assert all(d.score == 1.0 for d in detections)


def test_detect_preserve_last_zero_uses_full_bbox() -> None:
    """preserve_last=0 still produces a detection (full redaction)."""
    doc = _make_pdf("1234-5678-9012-3456")
    profile = _profile([AccountNumber(value="1234567890123456", preserve_last=0)])
    detections = detect_account_numbers(doc, profile)
    assert len(detections) >= 1
    assert detections[0].preserve_last == 0


def test_find_empty_account_value_returns_empty() -> None:
    """Account with no digits returns no matches."""
    assert _digits_only("") == ""
    no_digit_acct = AccountNumber(value="no-digits", preserve_last=1)
    assert _find_account_in_text("some text 1234", no_digit_acct) == []


def test_mask_empty_string() -> None:
    """mask_account_number on empty string returns empty string."""
    assert mask_account_number("", 4) == ""


def test_detect_page_with_no_text_blocks() -> None:
    """PDF page with no text blocks returns empty detections."""
    doc = fitz.open()
    doc.new_page()  # blank page, no text
    buf = doc.tobytes()
    doc2 = fitz.open(stream=buf, filetype="pdf")
    profile = _profile([AccountNumber(value="1234567890123456", preserve_last=4)])
    assert detect_account_numbers(doc2, profile) == []


def test_prefix_bbox_returns_none_when_all_digits_preserved() -> None:
    """_prefix_bbox returns None when preserve_last >= number of digits."""
    from redactron.redact.partial import _prefix_bbox
    doc = _make_pdf("12")
    page = doc[0]
    # "12" has 2 digits; preserve_last=4 means nothing to redact
    result = _prefix_bbox(page, "12", 0, 2, 4)
    assert result is None


def test_prefix_bbox_returns_none_when_text_not_found() -> None:
    """_prefix_bbox returns None when full_text is not in page rawdict."""
    from redactron.redact.partial import _prefix_bbox
    doc = _make_pdf("hello world")
    page = doc[0]
    # full_text not present on page
    result = _prefix_bbox(page, "9999999999999999", 0, 16, 4)
    assert result is None


def test_detect_prefix_bbox_fallback_when_none() -> None:
    """When _prefix_bbox returns None, detection falls back to span bbox."""
    # Use a 2-digit account with preserve_last=4 (more than digits) -> None from _prefix_bbox
    doc = _make_pdf("Account: 12")
    profile = _profile([AccountNumber(value="12", preserve_last=4)])
    detections = detect_account_numbers(doc, profile)
    # Should still produce a detection using span bbox fallback
    assert len(detections) >= 1


def test_detect_multipage_pdf() -> None:
    """Account number found on page 2 has correct page_num."""
    doc = fitz.open()
    doc.new_page()  # page 0 — no account
    page1 = doc.new_page()  # page 1
    page1.insert_text((72, 100), "1234-5678-9012-3456", fontsize=12)
    buf = doc.tobytes()
    doc2 = fitz.open(stream=buf, filetype="pdf")
    profile = _profile([AccountNumber(value="1234567890123456", preserve_last=4)])
    detections = detect_account_numbers(doc2, profile)
    assert len(detections) >= 1
    assert detections[0].page_num == 1


# --- Account number multi-line test (STEP 3) ---


@_pytest.mark.skip(
    reason=(
        "v1 limitation: account numbers split across line breaks are not supported. "
        "PyMuPDF rawdict processes spans independently; a hyphenated number split "
        "across lines appears as two separate spans with no structural link. "
        "Documented in docs/PROFILE.md. Add to v2 backlog."
    )
)
def test_account_number_split_across_lines() -> None:
    """Account number split across a line break — both halves redacted."""
    # This would require cross-span joining logic in detect_account_numbers,
    # which is deferred to v2.
    pass
