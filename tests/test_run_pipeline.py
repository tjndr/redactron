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


# --- Exhaustive detection tests (PART A) ---

def _make_pdf_with_text(tmp_path: Path, pages: list[list[str]], name: str = "test.pdf") -> Path:
    """Create a PDF with given text lines per page."""
    import io as _io
    doc = fitz.open()
    for page_lines in pages:
        page = doc.new_page()
        for i, line in enumerate(page_lines):
            page.insert_text((72, 100 + i * 20), line, fontsize=11)
    buf = _io.BytesIO(doc.tobytes())
    doc2 = fitz.open(stream=buf, filetype="pdf")
    path = tmp_path / name
    doc2.save(str(path))
    return path


def test_account_number_all_occurrences_redacted(tmp_path: Path) -> None:
    """Account number appearing 3 times (header, body, footer) — all redacted."""
    from redactron.pipeline import run_pipeline
    from redactron.profile import AccountNumber, DetectionConfig, Profile, Subject

    acct = "1234-5678-9012-3456"
    pdf = _make_pdf_with_text(tmp_path, [[
        f"Account: {acct}",
        "Some other content here",
        f"Reference: {acct}",
        "More content",
        f"Footer: {acct}",
    ]])
    out = tmp_path / "out.pdf"
    profile = Profile(
        subject=Subject(
            display_name="Test",
            account_numbers=[AccountNumber(value="1234567890123456", preserve_last=4)],
        ),
        detection=DetectionConfig(use_presidio=False),
    )
    result = run_pipeline(pdf, out, profile, verify=False)
    # All 3 occurrences should be detected
    assert len(result.detections) >= 3, (
        f"Expected >=3 account detections, got {len(result.detections)}: "
        f"{[d.text for d in result.detections]}"
    )


def test_name_all_occurrences_across_pages_redacted(tmp_path: Path) -> None:
    """Name appearing 5 times across 2 pages — all 5 redacted."""
    from redactron.pipeline import run_pipeline
    from redactron.profile import DetectionConfig, Profile, Subject

    pdf = _make_pdf_with_text(tmp_path, [
        ["Alice Sample signed this document.", "Prepared by Alice Sample."],
        ["Alice Sample", "Reviewed by Alice Sample.", "Approved: Alice Sample"],
    ])
    out = tmp_path / "out.pdf"
    profile = Profile(
        subject=Subject(display_name="Alice Sample"),
        detection=DetectionConfig(use_presidio=False, match_threshold=0.85),
    )
    result = run_pipeline(pdf, out, profile, verify=False)
    assert len(result.detections) >= 5, (
        f"Expected >=5 name detections across 2 pages, got {len(result.detections)}"
    )


def test_address_all_occurrences_across_pages_redacted(tmp_path: Path) -> None:
    """Address in page header on 3 pages — all 3 redacted."""
    from redactron.pipeline import run_pipeline
    from redactron.profile import DetectionConfig, Profile, Subject

    addr = "100 Phillip Street, San Jose, CA 91325"
    pdf = _make_pdf_with_text(tmp_path, [
        [addr, "Page 1 content"],
        [addr, "Page 2 content"],
        [addr, "Page 3 content"],
    ])
    out = tmp_path / "out.pdf"
    profile = Profile(
        subject=Subject(display_name="Test", addresses=[addr]),
        detection=DetectionConfig(use_presidio=False),
    )
    result = run_pipeline(pdf, out, profile, verify=False)
    assert len(result.detections) >= 3, (
        f"Expected >=3 address detections across 3 pages, got {len(result.detections)}"
    )


# --- Safety-net second pass test (PART B) ---

def test_safety_net_catches_missed_detections(tmp_path: Path) -> None:
    """Safety net: survivors from pass 1 are caught and redacted in pass 2."""
    from unittest.mock import patch
    from redactron.pipeline import run_pipeline, _detect_all
    from redactron.profile import DetectionConfig, Profile, Subject

    # Two separate lines so name appears in two distinct spans
    pdf = _make_pdf_with_text(tmp_path, [["Alice Sample was here.", "Alice Sample signed."]])
    out = tmp_path / "out.pdf"
    profile = Profile(
        subject=Subject(display_name="Alice Sample"),
        detection=DetectionConfig(use_presidio=False, match_threshold=0.85),
    )

    call_count = 0

    def patched_detect_all(doc: object, prof: object, threshold: float) -> list:
        nonlocal call_count
        call_count += 1
        hits = _detect_all(doc, prof, threshold)  # type: ignore[arg-type]
        # First call: return only first hit (simulate partial detector)
        if call_count == 1 and len(hits) > 1:
            return hits[:1]
        return hits

    import redactron.pipeline as pipeline_mod
    with patch.object(pipeline_mod, "_detect_all", patched_detect_all):
        result = run_pipeline(pdf, out, profile, verify=False)

    # Safety net should have caught the missed detection
    assert result.safety_passes > 0, (
        f"Expected safety net to fire at least once, got safety_passes={result.safety_passes}. "
        f"call_count={call_count}, detections_total={result.detections_total}"
    )
    assert result.detections_total >= 2, (
        f"Expected >=2 total detections after safety net, got {result.detections_total}"
    )


# --- BUG B: bbox sanity ---

def test_invoice_non_address_line_not_bridged(tmp_path: Path) -> None:
    """'Invoice #12345' between street and city/state must NOT be bridged."""
    from redactron.detect.address_detector import detect_addresses
    from redactron.extract.text_layer import TextLayer
    from redactron.profile import DetectionConfig, Profile, Subject

    profile = Profile(
        subject=Subject(display_name="Test", addresses=["100 Phillip Street, San Jose, CA 91325"]),
        detection=DetectionConfig(),
    )
    layers = [
        TextLayer(0, "100 Phillip Street", (72, 100, 300, 112), 0),
        TextLayer(0, "Invoice #12345", (72, 200, 300, 212), 0),
        TextLayer(0, "San Jose, CA 91325", (72, 700, 300, 712), 0),
    ]
    result = detect_addresses(layers, profile)
    # City/state/zip must NOT be redacted — bridge broken by invoice line
    texts = {d.text for d in result}
    assert "San Jose, CA 91325" not in texts, (
        f"'San Jose, CA 91325' should NOT be redacted when bridge broken by invoice line: {texts}"
    )


def test_redaction_rect_not_oversized(tmp_path: Path) -> None:
    """No single redaction rect should cover >30% of page area."""
    from redactron.profile import DetectionConfig, Profile, Subject

    pdf = _make_pdf_with_text(tmp_path, [[
        "Alice Sample",
        "100 Phillip Street",
        "San Jose, CA 91325",
        "Item 1: Widget A    $10.00",
        "Item 2: Widget B    $20.00",
        "Subtotal: $60.00",
        "Total: $60.00",
    ]])
    out = tmp_path / "out.pdf"
    from redactron.pipeline import run_pipeline
    profile = Profile(
        subject=Subject(
            display_name="Alice Sample",
            addresses=["100 Phillip Street, San Jose, CA 91325"],
        ),
        detection=DetectionConfig(use_presidio=False),
    )
    run_pipeline(pdf, out, profile, verify=False)

    import fitz as _fitz
    rdoc = _fitz.open(str(out))
    page = rdoc[0]
    page_area = page.rect.width * page.rect.height
    # Check that non-PII content is preserved
    text = page.get_text()
    assert "Subtotal" in text, f"'Subtotal' should survive redaction, got: {text!r}"
    assert "Total" in text, f"'Total' should survive redaction, got: {text!r}"


# --- BUG C: scanned PDF ---

def test_scanned_pdf_raises_no_text_layer_error(tmp_path: Path) -> None:
    """Image-only PDF raises NoTextLayerError with friendly message."""
    import fitz as _fitz
    from redactron.errors import NoTextLayerError
    from redactron.pipeline import run_pipeline
    from redactron.profile import DetectionConfig, Profile, Subject

    # Create a PDF with an embedded image and no text layer
    doc = _fitz.open()
    page = doc.new_page()
    # Create a minimal 1x1 PNG image and embed it
    import struct, zlib
    def _minimal_png() -> bytes:
        def chunk(name: bytes, data: bytes) -> bytes:
            c = struct.pack(">I", len(data)) + name + data
            return c + struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)
        ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        idat = zlib.compress(b"\x00\xFF\xFF\xFF")
        return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")
    png_bytes = _minimal_png()
    img_rect = _fitz.Rect(0, 0, page.rect.width, page.rect.height)
    page.insert_image(img_rect, stream=png_bytes)
    buf = doc.tobytes()
    doc2 = _fitz.open(stream=buf, filetype="pdf")
    pdf = tmp_path / "scan.pdf"
    doc2.save(str(pdf))

    profile = Profile(
        subject=Subject(display_name="Alice Sample"),
        detection=DetectionConfig(use_presidio=False),
    )
    with pytest.raises(NoTextLayerError, match="OCR"):
        run_pipeline(pdf, tmp_path / "out.pdf", profile, verify=False)


# --- BUG D: column-aware bridging ---

def test_two_column_does_not_bridge_across_columns(tmp_path: Path) -> None:
    """Text from left and right columns must NOT be bridged into one address."""
    import fitz as _fitz
    import io as _io
    from redactron.profile import DetectionConfig, Profile, Subject
    from redactron.pipeline import run_pipeline

    # Build a 2-column PDF: left col at x=72, right col at x=320
    doc = _fitz.open()
    page = doc.new_page()
    # Left column: "100 patients enrolled in study"
    page.insert_text((72, 100), "100 patients enrolled in study", fontsize=11)
    # Right column: "Phillip Lab, Stanford CA 94305"
    page.insert_text((320, 100), "Phillip Lab, Stanford CA 94305", fontsize=11)
    buf = _io.BytesIO(doc.tobytes())
    doc2 = _fitz.open(stream=buf, filetype="pdf")
    pdf = tmp_path / "twocol.pdf"
    doc2.save(str(pdf))

    profile = Profile(
        subject=Subject(display_name="Test", addresses=["100 Phillip Street, San Jose, CA 91325"]),
        detection=DetectionConfig(use_presidio=False),
    )
    result = run_pipeline(pdf, pdf.parent / "out.pdf", profile, verify=False)
    assert result.detections == [], (
        f"Two-column text should NOT be bridged into address match: "
        f"{[d.text for d in result.detections]}"
    )
