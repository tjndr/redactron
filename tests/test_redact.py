"""Tests for src/redactron/redact/engine.py."""

import io
from pathlib import Path

import fitz
import pytest

from redactron.detect.presidio_detector import Detection
from redactron.extract.text_layer import extract_text_layers
from redactron.redact.engine import redact, save_redacted


def _make_pdf(text: str) -> fitz.Document:
    """Create a reloadable in-memory PDF with the given text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    buf = io.BytesIO(doc.tobytes())
    return fitz.open(stream=buf, filetype="pdf")


def _detection(
    text: str,
    bbox: tuple[float, float, float, float] = (72.0, 59.0, 200.0, 76.0),
) -> Detection:
    return Detection(text=text, entity_type="PERSON", score=0.9, page_num=0, bbox=bbox)


def test_redact_returns_document() -> None:
    doc = _make_pdf("Hello World")
    result = redact(doc, [])
    assert isinstance(result, fitz.Document)


def test_redact_does_not_mutate_original() -> None:
    doc = _make_pdf("Secret Name")
    layers_before = extract_text_layers(doc)
    det = _detection("Secret Name")
    redact(doc, [det])
    layers_after = extract_text_layers(doc)
    assert layers_before == layers_after


def test_redact_no_detections_preserves_text() -> None:
    doc = _make_pdf("Hello World")
    result = redact(doc, [])
    layers = extract_text_layers(result)
    combined = " ".join(layer.text for layer in layers)
    assert "Hello" in combined


def test_redacted_text_not_recoverable() -> None:
    """Core verification: redacted text must not appear in re-extracted layers."""
    doc = _make_pdf("Tejinder Singh")
    # Get the actual bbox from extraction
    layers = extract_text_layers(doc)
    assert len(layers) > 0
    # Use the full page bbox to ensure we cover the text
    page = doc[0]
    full_bbox = (0.0, 0.0, float(page.rect.width), float(page.rect.height))
    det = _detection("Tejinder Singh", bbox=full_bbox)

    result = redact(doc, [det])
    result_layers = extract_text_layers(result)
    combined = " ".join(layer.text for layer in result_layers)
    assert "Tejinder" not in combined
    assert "Singh" not in combined


def test_redact_multipage_only_affects_target_page() -> None:
    doc = fitz.open()
    for i in range(2):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i} content", fontsize=12)
    buf = io.BytesIO(doc.tobytes())
    doc2 = fitz.open(stream=buf, filetype="pdf")

    page0 = doc2[0]
    full_bbox = (0.0, 0.0, float(page0.rect.width), float(page0.rect.height))
    det = Detection(text="Page 0 content", entity_type="PERSON", score=0.9,
                    page_num=0, bbox=full_bbox)

    result = redact(doc2, [det])
    layers = extract_text_layers(result)
    page1_text = " ".join(layer.text for layer in layers if layer.page_num == 1)
    assert "Page 1" in page1_text


def test_save_redacted_writes_file(tmp_path: Path) -> None:
    doc = _make_pdf("test")
    result = redact(doc, [])
    out = tmp_path / "out.pdf"
    save_redacted(result, out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_save_redacted_creates_parent_dirs(tmp_path: Path) -> None:
    doc = _make_pdf("test")
    result = redact(doc, [])
    out = tmp_path / "nested" / "dir" / "out.pdf"
    save_redacted(result, out)
    assert out.exists()


def test_save_redacted_output_is_valid_pdf(tmp_path: Path) -> None:
    doc = _make_pdf("test")
    result = redact(doc, [])
    out = tmp_path / "out.pdf"
    save_redacted(result, out)
    reopened = fitz.open(str(out))
    assert len(reopened) == 1


def test_redact_empty_detections_list() -> None:
    doc = _make_pdf("nothing to redact")
    result = redact(doc, [])
    assert len(result) == 1


def test_save_redacted_bad_path_raises(tmp_path: Path) -> None:
    from unittest.mock import patch

    doc = _make_pdf("test")
    result = redact(doc, [])
    with patch.object(result, "save", side_effect=RuntimeError("disk full")):
        with pytest.raises(Exception):
            save_redacted(result, tmp_path / "out.pdf")


def test_redact_raises_on_bad_page_num() -> None:
    doc = _make_pdf("test")
    det = Detection(
        text="test", entity_type="PERSON", score=0.9,
        page_num=99,  # out of range
        bbox=(0.0, 0.0, 100.0, 100.0),
    )
    with pytest.raises(Exception):
        redact(doc, [det])
