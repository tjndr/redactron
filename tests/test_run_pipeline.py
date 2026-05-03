"""Integration test: profile-driven detection wired into run pipeline (BLD-30).

This test MUST FAIL before the fix and PASS after.
"""

from __future__ import annotations

import io
from pathlib import Path

import fitz
import pytest

from redactron.profile import DetectionConfig, Profile, Subject


def _make_demo_pdf(tmp_path: Path) -> Path:
    """Create a 1-page PDF with known PII and non-PII content."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Alice Sample lives at 100 Test St, Springfield, IL 62701.", fontsize=12)
    page.insert_text((72, 120), "Acquired 2024-03-15 at $1,234.56.", fontsize=12)
    page.insert_text((72, 140), "Other Person lives at 500 Other Ave, Other City, NY 10001.", fontsize=12)
    buf = io.BytesIO(doc.tobytes())
    doc2 = fitz.open(stream=buf, filetype="pdf")
    path = tmp_path / "demo.pdf"
    doc2.save(str(path))
    return path


def _profile_no_presidio() -> Profile:
    return Profile(
        subject=Subject(
            display_name="Alice Sample",
            aliases=["A. Sample"],
            addresses=["100 Test St, Springfield, IL 62701"],
        ),
        detection=DetectionConfig(use_presidio=False, presidio_entities=[]),
    )


def test_profile_name_is_redacted(tmp_path: Path) -> None:
    """Profile display_name must appear in redacted spans."""
    from redactron.pipeline import run_pipeline

    pdf = _make_demo_pdf(tmp_path)
    out = tmp_path / "out.pdf"
    result = run_pipeline(pdf, out, _profile_no_presidio(), verify=False)
    redacted_texts = {d.text for d in result.detections}
    assert any("Alice Sample" in t or "Alice" in t for t in redacted_texts), (
        f"Expected 'Alice Sample' in detections, got: {redacted_texts}"
    )


def test_profile_address_is_redacted(tmp_path: Path) -> None:
    """Profile address must appear in redacted spans."""
    from redactron.pipeline import run_pipeline

    pdf = _make_demo_pdf(tmp_path)
    out = tmp_path / "out.pdf"
    result = run_pipeline(pdf, out, _profile_no_presidio(), verify=False)
    redacted_texts = {d.text for d in result.detections}
    assert any("Test St" in t or "Springfield" in t for t in redacted_texts), (
        f"Expected address in detections, got: {redacted_texts}"
    )


def test_dates_and_amounts_not_redacted(tmp_path: Path) -> None:
    """Dates and dollar amounts must NOT be redacted when use_presidio=False."""
    from redactron.pipeline import run_pipeline

    pdf = _make_demo_pdf(tmp_path)
    out = tmp_path / "out.pdf"
    result = run_pipeline(pdf, out, _profile_no_presidio(), verify=False)
    redacted_texts = {d.text for d in result.detections}
    assert not any("2024" in t for t in redacted_texts), (
        f"Date '2024-03-15' should NOT be redacted, got: {redacted_texts}"
    )
    assert not any("1,234" in t for t in redacted_texts), (
        f"Amount '$1,234.56' should NOT be redacted, got: {redacted_texts}"
    )


def test_other_person_not_redacted(tmp_path: Path) -> None:
    """Names and addresses not in profile must NOT be redacted."""
    from redactron.pipeline import run_pipeline

    pdf = _make_demo_pdf(tmp_path)
    out = tmp_path / "out.pdf"
    result = run_pipeline(pdf, out, _profile_no_presidio(), verify=False)
    redacted_texts = {d.text for d in result.detections}
    assert not any("Other Person" in t for t in redacted_texts), (
        f"'Other Person' should NOT be redacted, got: {redacted_texts}"
    )
    assert not any("500 Other" in t for t in redacted_texts), (
        f"'500 Other Ave' should NOT be redacted, got: {redacted_texts}"
    )
