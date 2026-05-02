"""PyMuPDF redaction engine.

Applies redaction annotations to a PDF document for each Detection and
writes the result to a new file. The original document is never mutated.
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

from redactron.detect.presidio_detector import Detection
from redactron.errors import RedactionError


def redact(doc: fitz.Document, detections: list[Detection]) -> fitz.Document:
    """Apply redaction annotations and return a new redacted document.

    The input *doc* is not mutated. A copy is made, annotated, and
    redactions are applied before returning.

    Args:
        doc: Source PDF document (read-only).
        detections: PII detections to redact.

    Returns:
        A new fitz.Document with redactions applied.

    Raises:
        RedactionError: If applying redactions fails.
    """
    try:
        # Work on an in-memory copy so the original is never mutated.
        buf = doc.tobytes()
        out = fitz.open(stream=buf, filetype="pdf")

        # Group detections by page for efficiency.
        by_page: dict[int, list[Detection]] = {}
        for det in detections:
            by_page.setdefault(det.page_num, []).append(det)

        for page_num, page_detections in by_page.items():
            page = out[page_num]
            for det in page_detections:
                rect = fitz.Rect(det.bbox)
                page.add_redact_annot(rect, fill=(0, 0, 0))
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

        return out
    except RedactionError:
        raise
    except Exception as exc:
        raise RedactionError("Failed to apply redactions") from exc


def save_redacted(doc: fitz.Document, output_path: Path) -> None:
    """Save a redacted document to disk.

    Args:
        doc: Redacted fitz.Document.
        output_path: Destination path for the output PDF.

    Raises:
        RedactionError: If saving fails.
    """
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path), garbage=4, deflate=True)
    except Exception as exc:
        raise RedactionError(f"Failed to save redacted PDF to {output_path}") from exc
