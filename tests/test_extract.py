"""Tests for src/redactron/extract/text_layer.py and ocr.py."""

import io
from pathlib import Path
from unittest.mock import patch

import fitz
import pytest

from redactron.errors import ExtractionError
from redactron.extract.ocr import (
    CONF_THRESHOLD,
    DEFAULT_DPI,
    OcrPageResult,
    OcrWord,
    _is_image_page,
    ocr_page,
    paint_ocr_redactions,
)
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


# ---------------------------------------------------------------------------
# OCR module tests (BLD-19)
# ---------------------------------------------------------------------------


def _make_image_pdf() -> fitz.Document:
    """Create a single-page PDF with an embedded image and no text layer."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    # Insert a small white rectangle as a stand-in image (no text)
    page.draw_rect(fitz.Rect(0, 0, 612, 792), color=(1, 1, 1), fill=(1, 1, 1))
    buf = io.BytesIO(doc.tobytes())
    return fitz.open(stream=buf, filetype="pdf")


def _make_text_pdf() -> fitz.Document:
    """Create a single-page PDF with a text layer (>50 chars)."""
    doc = fitz.open()
    page = doc.new_page()
    # Long enough to exceed the 50-char image-page threshold
    page.insert_text((72, 72), "Hello World this is a text page with enough content", fontsize=12)
    buf = io.BytesIO(doc.tobytes())
    return fitz.open(stream=buf, filetype="pdf")


def _mock_tesseract_data(words: list[tuple[str, int, int, int, int, int, int]]) -> dict:
    """Build a pytesseract image_to_data DICT result.

    Each tuple: (text, conf, left, top, width, height, level)
    """
    return {
        "text": [w[0] for w in words],
        "conf": [w[1] for w in words],
        "left": [w[2] for w in words],
        "top": [w[3] for w in words],
        "width": [w[4] for w in words],
        "height": [w[5] for w in words],
        "level": [w[6] for w in words],
    }


def test_is_image_page_true_for_empty_page() -> None:
    doc = _make_image_pdf()
    assert _is_image_page(doc[0]) is True


def test_is_image_page_false_for_text_page() -> None:
    doc = _make_text_pdf()
    assert _is_image_page(doc[0]) is False


def test_ocr_word_dataclass_frozen() -> None:
    w = OcrWord(page_num=0, text="hello", bbox=(0.0, 0.0, 10.0, 10.0), conf=90)
    with pytest.raises(Exception):
        w.text = "changed"  # type: ignore[misc]


def test_ocr_page_returns_result_with_words() -> None:
    """ocr_page with mocked tesseract returns OcrWord list."""
    doc = _make_image_pdf()
    page = doc[0]

    mock_data = _mock_tesseract_data([
        ("Alice", 95, 100, 100, 50, 15, 5),
        ("Smith", 90, 160, 100, 50, 15, 5),
    ])

    with patch("pytesseract.image_to_data", return_value=mock_data):
        result = ocr_page(page, page_num=0, dpi=DEFAULT_DPI)

    assert isinstance(result, OcrPageResult)
    assert len(result.words) == 2
    assert result.words[0].text == "Alice"
    assert result.words[1].text == "Smith"
    assert result.low_conf_count == 0


def test_ocr_page_dpi_scale_applied() -> None:
    """Pixel coords are scaled by 72/dpi to PDF points."""
    doc = _make_image_pdf()
    page = doc[0]
    dpi = 300
    scale = 72.0 / dpi  # 0.24

    mock_data = _mock_tesseract_data([
        ("Test", 95, 100, 200, 60, 20, 5),
    ])

    with patch("pytesseract.image_to_data", return_value=mock_data):
        result = ocr_page(page, page_num=0, dpi=dpi)

    assert len(result.words) == 1
    x0, y0, x1, y1 = result.words[0].bbox
    assert abs(x0 - 100 * scale) < 0.01
    assert abs(y0 - 200 * scale) < 0.01
    assert abs(x1 - (100 + 60) * scale) < 0.01
    assert abs(y1 - (200 + 20) * scale) < 0.01


def test_ocr_page_low_conf_words_skipped() -> None:
    """Words below CONF_THRESHOLD are counted but not returned."""
    doc = _make_image_pdf()
    page = doc[0]

    mock_data = _mock_tesseract_data([
        ("Good", 95, 10, 10, 30, 12, 5),
        ("Bad", CONF_THRESHOLD - 1, 50, 10, 30, 12, 5),
    ])

    with patch("pytesseract.image_to_data", return_value=mock_data):
        result = ocr_page(page, page_num=0)

    assert len(result.words) == 1
    assert result.words[0].text == "Good"
    assert result.low_conf_count == 1


def test_ocr_page_oversized_bbox_rejected() -> None:
    """A word bbox covering >30% of page area is rejected."""
    doc = _make_image_pdf()
    page = doc[0]
    # page is 612×792 pt; at 300 DPI that's 2550×3300 px
    # A word covering 50% of the image in pixels → >30% of page area
    mock_data = _mock_tesseract_data([
        ("HUGE", 95, 0, 0, 2550, 1650, 5),  # 50% of page height
    ])

    with patch("pytesseract.image_to_data", return_value=mock_data):
        result = ocr_page(page, page_num=0)

    assert len(result.words) == 0


def test_ocr_page_empty_text_skipped() -> None:
    """Empty/whitespace text entries are ignored."""
    doc = _make_image_pdf()
    page = doc[0]

    mock_data = _mock_tesseract_data([
        ("", 95, 10, 10, 30, 12, 5),
        ("  ", 95, 50, 10, 30, 12, 5),
        ("Real", 95, 90, 10, 30, 12, 5),
    ])

    with patch("pytesseract.image_to_data", return_value=mock_data):
        result = ocr_page(page, page_num=0)

    assert len(result.words) == 1
    assert result.words[0].text == "Real"


def test_paint_ocr_redactions_paints_matching_words() -> None:
    """paint_ocr_redactions draws rects for matching PII words."""
    doc = _make_image_pdf()
    page = doc[0]

    words = [
        OcrWord(page_num=0, text="Alice", bbox=(10.0, 10.0, 50.0, 25.0), conf=95),
        OcrWord(page_num=0, text="Smith", bbox=(60.0, 10.0, 100.0, 25.0), conf=95),
        OcrWord(page_num=0, text="Invoice", bbox=(10.0, 40.0, 80.0, 55.0), conf=95),
    ]

    count = paint_ocr_redactions(page, words, {"Alice", "Smith"})
    assert count == 2


def test_paint_ocr_redactions_case_insensitive() -> None:
    """Matching is case-insensitive."""
    doc = _make_image_pdf()
    page = doc[0]

    words = [OcrWord(page_num=0, text="ALICE", bbox=(10.0, 10.0, 50.0, 25.0), conf=95)]
    count = paint_ocr_redactions(page, words, {"alice"})
    assert count == 1


def test_paint_ocr_redactions_no_match_returns_zero() -> None:
    doc = _make_image_pdf()
    page = doc[0]

    words = [OcrWord(page_num=0, text="Invoice", bbox=(10.0, 10.0, 80.0, 25.0), conf=95)]
    count = paint_ocr_redactions(page, words, {"Alice"})
    assert count == 0


def test_ocr_detections_appended_to_pipeline_result(tmp_path: Path) -> None:
    """OCR-redacted files show correct detection count (not 0)."""
    from unittest.mock import patch

    import fitz

    from redactron.pipeline import run_pipeline
    from redactron.profile import Profile

    profile = Profile.model_validate({
        "version": 1,
        "subject": {"display_name": "Alice"},
        "detection": {"use_presidio": False, "presidio_entities": []},
    })

    # Image-only PDF (no text layer)
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.draw_rect(fitz.Rect(0, 0, 612, 792), color=(1, 1, 1), fill=(1, 1, 1))
    pdf_path = tmp_path / "scan.pdf"
    doc.save(str(pdf_path))

    mock_data = {
        "text": ["Alice"], "conf": [95],
        "left": [100], "top": [100], "width": [50], "height": [15], "level": [5],
    }

    with patch("pytesseract.image_to_data", return_value=mock_data):
        result = run_pipeline(
            pdf_path, tmp_path / "out.pdf", profile,
            verify=False, write_reports=False, ocr_enabled=True,
        )

    assert result.detections_total > 0, "OCR detections should be counted"
    assert any(d.entity_type == "OCR" for d in result.detections), \
        "Detections should include OCR entries"
