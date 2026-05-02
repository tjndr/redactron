"""Tests for src/redactron/extract/text_layer.py."""

import io
from pathlib import Path

import fitz
import pytest

from redactron.errors import ExtractionError
from redactron.extract.text_layer import TextLayer, extract_text_layers, open_pdf


def _make_pdf(text: str) -> fitz.Document:
    """Create an in-memory single-page PDF with the given text.

    Must save/reload so PyMuPDF builds the text layer index.
    """
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    buf = io.BytesIO(doc.tobytes())
    return fitz.open(stream=buf, filetype="pdf")


def test_extract_returns_text_layers() -> None:
    doc = _make_pdf("Hello World")
    layers = extract_text_layers(doc)
    assert len(layers) > 0
    assert all(isinstance(layer, TextLayer) for layer in layers)


def test_extracted_text_contains_content() -> None:
    doc = _make_pdf("Tejinder Singh")
    layers = extract_text_layers(doc)
    combined = " ".join(layer.text for layer in layers)
    assert "Tejinder" in combined


def test_bbox_is_four_floats() -> None:
    doc = _make_pdf("test")
    layers = extract_text_layers(doc)
    for layer in layers:
        assert len(layer.bbox) == 4
        assert all(isinstance(v, float) for v in layer.bbox)


def test_bbox_coordinates_are_positive() -> None:
    doc = _make_pdf("test")
    layers = extract_text_layers(doc)
    for layer in layers:
        x0, y0, x1, y1 = layer.bbox
        assert x1 > x0
        assert y1 > y0


def test_page_num_is_zero_for_single_page() -> None:
    doc = _make_pdf("test")
    layers = extract_text_layers(doc)
    assert all(layer.page_num == 0 for layer in layers)


def test_multipage_page_nums() -> None:
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i}", fontsize=12)
    buf = io.BytesIO(doc.tobytes())
    doc2 = fitz.open(stream=buf, filetype="pdf")
    layers = extract_text_layers(doc2)
    page_nums = {layer.page_num for layer in layers}
    assert page_nums == {0, 1, 2}


def test_empty_page_returns_no_layers() -> None:
    doc = fitz.open()
    doc.new_page()
    buf = io.BytesIO(doc.tobytes())
    doc2 = fitz.open(stream=buf, filetype="pdf")
    layers = extract_text_layers(doc2)
    assert layers == []


def test_block_type_is_zero_for_text() -> None:
    doc = _make_pdf("test")
    layers = extract_text_layers(doc)
    assert all(layer.block_type == 0 for layer in layers)


def test_open_pdf_missing_file_raises() -> None:
    with pytest.raises(ExtractionError, match="Cannot open PDF"):
        open_pdf(Path("/nonexistent/file.pdf"))


def test_open_pdf_returns_document(tmp_path: Path) -> None:
    pdf_path = tmp_path / "test.pdf"
    doc = _make_pdf("hello")
    doc.save(str(pdf_path))
    opened = open_pdf(pdf_path)
    assert len(opened) == 1


def test_open_pdf_encrypted_raises(tmp_path: Path) -> None:
    pdf_path = tmp_path / "enc.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf_path), encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="secret")
    with pytest.raises(ExtractionError, match="encrypted"):
        open_pdf(pdf_path)


def test_span_with_no_chars_skipped() -> None:
    """Spans with empty chars list produce no TextLayer."""
    doc = fitz.open()
    doc.new_page()
    buf = io.BytesIO(doc.tobytes())
    doc2 = fitz.open(stream=buf, filetype="pdf")
    layers = extract_text_layers(doc2)
    assert layers == []


def test_extract_text_layers_page_error_raises() -> None:
    """Simulate a page parse failure by passing a non-Document object."""
    from unittest.mock import MagicMock

    mock_doc = MagicMock()
    mock_doc.__len__ = MagicMock(return_value=1)
    mock_page = MagicMock()
    mock_page.get_text.side_effect = RuntimeError("parse error")
    mock_doc.__getitem__ = MagicMock(return_value=mock_page)

    with pytest.raises(ExtractionError, match="Failed to extract text"):
        extract_text_layers(mock_doc)
