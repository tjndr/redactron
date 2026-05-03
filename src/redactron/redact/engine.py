"""PyMuPDF redaction engine with bbox sanity guards.

Applies redaction annotations to a PDF document for each Detection.
Rejects oversized rects (>30% of page area or >4x median line height)
to prevent accidental large-region blanking from detector bugs.
"""

from __future__ import annotations

import logging
import statistics
from pathlib import Path

import fitz  # PyMuPDF

from redactron.detect.presidio_detector import Detection
from redactron.errors import RedactionError

log = logging.getLogger(__name__)

# Maximum fraction of page area a single redaction rect may cover
_MAX_RECT_PAGE_FRACTION = 0.30
# Maximum multiple of median line height a rect may be tall
_MAX_HEIGHT_LINE_MULTIPLE = 4.0


def _median_line_height(page: fitz.Page) -> float:
    """Estimate median text line height from rawdict spans."""
    heights: list[float] = []
    try:
        for block in page.get_text("rawdict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                bbox = line.get("bbox")
                if bbox:
                    heights.append(bbox[3] - bbox[1])
    except Exception:
        pass
    return statistics.median(heights) if heights else 12.0


def redact(doc: fitz.Document, detections: list[Detection]) -> fitz.Document:
    """Apply redaction annotations and return a new redacted document.

    Rejects any bbox that covers >30% of page area or is >4x median line
    height, logging a warning instead of applying the oversized rect.

    Args:
        doc: Source PDF document (read-only).
        detections: PII detections to redact.

    Returns:
        A new fitz.Document with redactions applied.

    Raises:
        RedactionError: If applying redactions fails.
    """
    try:
        buf = doc.tobytes()
        out = fitz.open(stream=buf, filetype="pdf")

        by_page: dict[int, list[Detection]] = {}
        for det in detections:
            by_page.setdefault(det.page_num, []).append(det)

        for page_num, page_detections in by_page.items():
            page = out[page_num]
            page_area = page.rect.width * page.rect.height
            median_lh = _median_line_height(page)

            for det in page_detections:
                rect = fitz.Rect(det.bbox)
                rect_area = rect.width * rect.height

                if rect_area > _MAX_RECT_PAGE_FRACTION * page_area:
                    log.warning(
                        "Redaction rect for %r covers %.0f%% of page — REJECTING "
                        "(detector bug; bbox too large).",
                        det.text[:40],
                        rect_area / page_area * 100,
                    )
                    continue

                if median_lh > 0 and rect.height > _MAX_HEIGHT_LINE_MULTIPLE * median_lh:
                    log.warning(
                        "Redaction rect for %r is %.1fx median line height — REJECTING.",
                        det.text[:40],
                        rect.height / median_lh,
                    )
                    continue

                page.add_redact_annot(rect, fill=(0, 0, 0))

            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=0)

        return out
    except RedactionError:
        raise
    except Exception as exc:
        raise RedactionError("Failed to apply redactions") from exc


def save_redacted(doc: fitz.Document, output_path: Path) -> None:
    """Save a redacted document to disk."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path), garbage=4, deflate=True)
    except Exception as exc:
        raise RedactionError(f"Failed to save redacted PDF to {output_path}") from exc
