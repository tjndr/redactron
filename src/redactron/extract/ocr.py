"""OCR fallback for image-only PDF pages via pytesseract.

Per-page auto-trigger: if a page has fewer than 50 characters of extractable
text, it is rendered at ``DEFAULT_DPI`` and passed through Tesseract.

Coordinate conversion
---------------------
Tesseract returns bounding boxes in *pixel space* at the render DPI.
PDF coordinates are in *points* (1 pt = 1/72 inch).  The scale factor is::

    scale = 72 / dpi          # e.g. 72/300 = 0.24

Applying this converts pixel coords → PDF points.  Omitting it would place
redaction boxes ~4× too large (at 300 DPI the raw pixel value is 4.17× the
point value).

Redaction strategy
------------------
OCR-derived spans have no underlying text stream to redact, so we paint the
image region black with ``page.draw_rect(rect, color=(0,0,0), fill=(0,0,0))``.
This is applied *before* ``page.apply_redactions()`` so the black fill is
baked into the page content stream.

Sanity guards (reused from redact/engine.py thresholds)
--------------------------------------------------------
* Reject any word bbox covering >30 % of page area.
* Reject any word bbox taller than 4× the median word height on that page.
  (Median is computed from the OCR word heights themselves for image pages.)
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field

import fitz  # PyMuPDF

log = logging.getLogger(__name__)

DEFAULT_DPI: int = 300
CONF_THRESHOLD: int = 60  # Tesseract confidence 0-100; below this → warn + skip

# Reuse the same guard constants as redact/engine.py
_MAX_RECT_PAGE_FRACTION = 0.30
_MAX_HEIGHT_WORD_MULTIPLE = 4.0


@dataclass(frozen=True, slots=True)
class OcrWord:
    """A single word detected by Tesseract with its PDF-space bounding box."""

    page_num: int
    text: str
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1 in PDF points
    conf: int  # Tesseract confidence 0-100


@dataclass
class OcrPageResult:
    """OCR result for a single page."""

    page_num: int
    words: list[OcrWord] = field(default_factory=list)
    low_conf_count: int = 0  # words below CONF_THRESHOLD (skipped)


def _is_image_page(page: fitz.Page, min_chars: int = 50) -> bool:
    """Return True if the page has fewer than min_chars of extractable text."""
    return len(page.get_text().strip()) < min_chars


def ocr_page(page: fitz.Page, page_num: int, dpi: int = DEFAULT_DPI) -> OcrPageResult:
    """Run Tesseract on a single fitz.Page and return word-level results.

    Args:
        page: The fitz.Page to OCR.
        page_num: Zero-based page index (for OcrWord.page_num).
        dpi: Render resolution.  Higher = more accurate but slower.

    Returns:
        OcrPageResult with words in PDF point coordinates.
    """
    import pytesseract
    from PIL import Image as _Image

    result = OcrPageResult(page_num=page_num)
    scale = 72.0 / dpi  # pixel → PDF point conversion factor

    # Render page to a PIL image at the requested DPI
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = _Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    # image_to_data returns a TSV-like dict with per-word bboxes + confidence
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    n = len(data["text"])
    heights: list[float] = []

    # First pass: collect heights for sanity guard median
    for i in range(n):
        try:
            conf = int(data["conf"][i])
        except (ValueError, TypeError):
            continue
        if conf < CONF_THRESHOLD:
            continue
        text = str(data["text"][i]).strip()
        if not text:
            continue
        h = float(data["height"][i]) * scale
        if h > 0:
            heights.append(h)

    median_h = statistics.median(heights) if heights else 12.0
    page_area = page.rect.width * page.rect.height

    # Second pass: build OcrWord list with sanity guards
    for i in range(n):
        try:
            conf = int(data["conf"][i])
        except (ValueError, TypeError):
            continue

        text = str(data["text"][i]).strip()
        if not text:
            continue

        if conf < CONF_THRESHOLD:
            result.low_conf_count += 1
            log.debug("OCR page %d: low-conf word %r (conf=%d) — skipped", page_num, text, conf)
            continue

        # Convert pixel bbox → PDF points
        x0 = float(data["left"][i]) * scale
        y0 = float(data["top"][i]) * scale
        x1 = x0 + float(data["width"][i]) * scale
        y1 = y0 + float(data["height"][i]) * scale
        w = x1 - x0
        h = y1 - y0

        rect_area = w * h
        if rect_area > _MAX_RECT_PAGE_FRACTION * page_area:
            log.warning(
                "OCR page %d: word %r bbox covers %.0f%% of page — REJECTING",
                page_num, text, rect_area / page_area * 100,
            )
            continue

        if median_h > 0 and h > _MAX_HEIGHT_WORD_MULTIPLE * median_h:
            log.warning(
                "OCR page %d: word %r bbox height %.1f is %.1fx median — REJECTING",
                page_num, text, h, h / median_h,
            )
            continue

        result.words.append(OcrWord(
            page_num=page_num,
            text=text,
            bbox=(x0, y0, x1, y1),
            conf=conf,
        ))

    if result.low_conf_count:
        log.warning(
            "OCR page %d: %d low-confidence word(s) skipped (threshold=%d)",
            page_num, result.low_conf_count, CONF_THRESHOLD,
        )

    return result


def ocr_document(
    doc: fitz.Document,
    dpi: int = DEFAULT_DPI,
    force: bool = False,
) -> list[OcrPageResult]:
    """OCR all image-only pages in a document.

    Args:
        doc: Open fitz.Document.
        dpi: Render DPI (default 300).
        force: If True, OCR every page regardless of text content.

    Returns:
        List of OcrPageResult, one per page that was OCR'd (skips text pages
        unless force=True).
    """
    results: list[OcrPageResult] = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        if not force and not _is_image_page(page):
            log.debug("OCR page %d: has text layer, skipping", page_num)
            continue
        log.info("OCR page %d: rendering at %d DPI", page_num, dpi)
        results.append(ocr_page(page, page_num, dpi=dpi))
    return results


def paint_ocr_redactions(
    page: fitz.Page,
    words: list[OcrWord],
    pii_texts: set[str],
) -> int:
    """Paint black rectangles over OCR words that match pii_texts.

    Uses image-region painting (draw_rect with black fill) rather than
    text-stream redaction, since image pages have no text stream.

    Args:
        page: The fitz.Page to paint on (mutated in place).
        words: OCR words for this page.
        pii_texts: Set of text strings to redact (case-insensitive match).

    Returns:
        Number of rectangles painted.
    """
    lower_pii = {t.lower() for t in pii_texts}
    count = 0
    for word in words:
        if word.text.lower() in lower_pii:
            rect = fitz.Rect(word.bbox)
            page.draw_rect(rect, color=(0, 0, 0), fill=(0, 0, 0))
            count += 1
    return count
