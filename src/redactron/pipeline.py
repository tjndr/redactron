"""Core redaction pipeline — profile-driven, testable, CLI-independent.

Orchestrates: extract → detect (profile-first) → redact → safety-net → verify.

Safety net: after applying redactions, re-extract and re-detect up to
MAX_PASSES times. If survivors are found, apply additional redactions.
This guards against any future detector gap without relying on the M3
verifier (which produces an audit report, not a runtime correction).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import fitz

from redactron.detect.presidio_detector import Detection
from redactron.errors import NoTextLayerError, RedactionError
from redactron.profile import Profile

log = logging.getLogger(__name__)

MAX_PASSES = 3


@dataclass
class PipelineResult:
    """Result of processing a single PDF."""

    input_path: Path
    output_path: Path
    detections: list[Detection] = field(default_factory=list)
    detections_total: int = 0       # cumulative across all passes
    safety_passes: int = 0          # number of safety passes that found survivors
    verification_passed: bool | None = None
    survivors: int = 0


def _detect_all(
    doc: fitz.Document,
    profile: Profile,
    score_threshold: float,
) -> list[Detection]:
    """Run all configured detectors and return merged detections."""
    from redactron.detect.account_detector import detect_custom_patterns
    from redactron.detect.address_detector import detect_addresses
    from redactron.detect.name_detector import detect_names
    from redactron.extract.text_layer import extract_text_layers
    from redactron.redact.partial import detect_account_numbers

    layers = extract_text_layers(doc)

    profile_hits: list[Detection] = []
    profile_hits.extend(detect_names(layers, profile))
    profile_hits.extend(detect_addresses(layers, profile))
    profile_hits.extend(detect_account_numbers(doc, profile))
    profile_hits.extend(detect_custom_patterns(layers, profile))

    presidio_hits: list[Detection] = []
    if profile.detection.use_presidio and profile.detection.presidio_entities:
        from redactron.detect.presidio_detector import detect as presidio_detect
        presidio_hits = presidio_detect(
            layers,
            entities=list(profile.detection.presidio_entities),
            score_threshold=score_threshold,
        )

    return _merge_detections(profile_hits, presidio_hits)


def _apply_redactions(doc: fitz.Document, detections: list[Detection]) -> None:
    """Apply redaction annotations in-place on doc (mutates doc)."""
    by_page: dict[int, list[Detection]] = {}
    for det in detections:
        by_page.setdefault(det.page_num, []).append(det)

    for page_num, page_dets in by_page.items():
        page = doc[page_num]
        for det in page_dets:
            page.add_redact_annot(fitz.Rect(det.bbox), fill=(0, 0, 0))
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=0)
        page.clean_contents()  # merge streams so redaction renders correctly in all viewers


def run_pipeline(
    input_path: Path,
    output_path: Path,
    profile: Profile,
    *,
    score_threshold: float = 0.5,
    verify: bool = True,
) -> PipelineResult:
    """Run the full redaction pipeline with safety-net multi-pass.

    Pass 1: detect all PII, apply redactions.
    Pass 2+: re-extract redacted PDF, re-detect. If survivors found, redact again.
    Stops when no survivors found or MAX_PASSES reached.

    Args:
        input_path: Source PDF path.
        output_path: Destination path for the redacted PDF.
        profile: Loaded and validated Profile.
        score_threshold: Minimum score for Presidio detections.
        verify: Whether to run post-redaction verification.

    Returns:
        PipelineResult with detections, safety_passes, and verification status.
    """
    from redactron.extract.text_layer import open_pdf

    log.info("Loaded profile: %s (subject: %s)", profile.name, profile.subject.display_name)
    log.info(
        "Detectors enabled: profile=True, presidio=%s, entities=%s",
        profile.detection.use_presidio,
        profile.detection.presidio_entities if profile.detection.use_presidio else [],
    )

    doc = open_pdf(input_path)

    # Pre-flight: detect image-only (scanned) PDFs
    total_chars = sum(len(page.get_text()) for page in doc)
    has_images = any(page.get_images() for page in doc)
    if total_chars < 50 and has_images:
        doc.close()
        raise NoTextLayerError(
            "❌ This PDF appears to be a scan or image-only document with no text layer.\n"
            "Redactron cannot detect text without OCR.\n"
            "OCR support is coming in v1 milestone M4. Until then:\n"
            "  1. Re-export from source application with 'searchable text', OR\n"
            "  2. Run an OCR tool first (e.g., `ocrmypdf input.pdf output.pdf`)\n"
            "     and pass the OCR'd file to redactron.\n"
            "Run with --debug to see per-page character counts."
        )
    # Work on an in-memory copy; mutate it across passes
    buf = doc.tobytes()
    working_doc = fitz.open(stream=buf, filetype="pdf")

    all_detections: list[Detection] = []
    safety_passes = 0

    for pass_num in range(1, MAX_PASSES + 1):
        spans = _detect_all(working_doc, profile, score_threshold)

        if not spans:
            if pass_num == 1:
                log.info("Pass 1: 0 spans detected, nothing to redact")
            else:
                log.info("Safety pass %d: 0 survivors detected, complete", pass_num)
            break

        if pass_num == 1:
            log.info(
                "Pass 1: %d spans detected across %d pages (profile=%d, presidio=%d)",
                len(spans),
                len({d.page_num for d in spans}),
                sum(1 for d in spans if d.entity_type != "PRESIDIO"),
                sum(1 for d in spans if d.entity_type == "PRESIDIO"),
            )
            all_detections = spans
        else:
            safety_passes += 1
            log.warning(
                "Safety pass %d: %d SURVIVORS detected — first-pass missed these. Redacting.",
                pass_num,
                len(spans),
            )
            all_detections.extend(spans)

        _apply_redactions(working_doc, spans)

    else:
        raise RedactionError(
            f"Redaction did not converge after {MAX_PASSES} passes. "
            "Possible causes: detector instability, adversarial input. "
            "Run with --debug to inspect."
        )

    if safety_passes > 0:
        log.warning(
            "WARNING: First-pass detection missed spans that the safety net caught. "
            "Consider opening a bug report with the input PDF (sensitive content removed)."
        )

    # Save the final working doc
    output_path.parent.mkdir(parents=True, exist_ok=True)
    working_doc.save(str(output_path), garbage=4, deflate=True)

    result = PipelineResult(
        input_path=input_path,
        output_path=output_path,
        detections=all_detections,
        detections_total=len(all_detections),
        safety_passes=safety_passes,
    )

    if verify:
        from redactron.verify.verifier import verify_redaction
        vr = verify_redaction(
            working_doc,
            profile,
            original_detections=all_detections,
            score_threshold=score_threshold,
        )
        result.verification_passed = vr.passed
        result.survivors = len(vr.survivors)

    return result


def _merge_detections(
    profile_hits: list[Detection],
    presidio_hits: list[Detection],
) -> list[Detection]:
    """Merge profile and Presidio hits; profile hits win on bbox overlap."""
    if not presidio_hits:
        return profile_hits

    profile_keys: set[tuple[int, tuple[float, float, float, float]]] = {
        (d.page_num, d.bbox) for d in profile_hits
    }
    filtered_presidio = [
        d for d in presidio_hits if not _overlaps_any(d, profile_keys)
    ]
    return profile_hits + filtered_presidio


def _overlaps_any(
    det: Detection,
    profile_keys: set[tuple[int, tuple[float, float, float, float]]],
) -> bool:
    x0, y0, x1, y1 = det.bbox
    for page_num, (px0, py0, px1, py1) in profile_keys:
        if det.page_num != page_num:
            continue
        if x0 < px1 and x1 > px0 and y0 < py1 and y1 > py0:
            return True
    return False
