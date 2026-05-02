"""PDF text extraction with character-level bounding boxes.

Uses PyMuPDF's rawdict output to get per-span text and bounding boxes,
which are later used to map Presidio detections back to page coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

from redactron.errors import ExtractionError


@dataclass(frozen=True, slots=True)
class TextLayer:
    """A single text span extracted from a PDF page."""

    page_num: int
    text: str
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1
    block_type: int  # 0 = text, 1 = image


def _span_text_and_bbox(
    span: dict,  # type: ignore[type-arg]
) -> tuple[str, tuple[float, float, float, float]] | None:
    """Extract text and bbox from a rawdict span.

    In rawdict mode the span-level ``text`` field is empty; text must be
    assembled from the ``chars`` list.  Returns None if the span is empty.
    """
    chars: list[dict] = span.get("chars", [])  # type: ignore[type-arg]
    if not chars:
        return None

    text = "".join(ch["c"] for ch in chars).strip()
    if not text:
        return None

    # Union bbox across all chars
    x0 = min(ch["bbox"][0] for ch in chars)
    y0 = min(ch["bbox"][1] for ch in chars)
    x1 = max(ch["bbox"][2] for ch in chars)
    y1 = max(ch["bbox"][3] for ch in chars)
    return text, (x0, y0, x1, y1)


def extract_text_layers(doc: fitz.Document) -> list[TextLayer]:
    """Extract all text spans with bounding boxes from a PDF document.

    Args:
        doc: An open fitz.Document.

    Returns:
        List of TextLayer objects, one per span across all pages.

    Raises:
        ExtractionError: If a page cannot be parsed.
    """
    layers: list[TextLayer] = []
    for page_num in range(len(doc)):
        try:
            page = doc[page_num]
            blocks = page.get_text("rawdict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        except Exception as exc:
            raise ExtractionError(f"Failed to extract text from page {page_num}") from exc

        for block in blocks:
            block_type: int = block["type"]
            if block_type != 0:  # skip image blocks
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    result = _span_text_and_bbox(span)
                    if result is None:
                        continue
                    text, bbox = result
                    layers.append(TextLayer(
                        page_num=page_num,
                        text=text,
                        bbox=bbox,
                        block_type=block_type,
                    ))
    return layers


def open_pdf(path: Path) -> fitz.Document:
    """Open a PDF file, raising ExtractionError on failure.

    Args:
        path: Path to the PDF file.

    Returns:
        An open fitz.Document.

    Raises:
        ExtractionError: If the file cannot be opened or is encrypted.
    """
    try:
        doc = fitz.open(str(path))
    except Exception as exc:
        raise ExtractionError(f"Cannot open PDF: {path}") from exc

    if doc.is_encrypted:
        raise ExtractionError(f"PDF is encrypted and cannot be processed: {path}")

    return doc
