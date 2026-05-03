"""Core redaction pipeline — profile-driven, testable, CLI-independent.

Orchestrates: extract → detect (profile-first) → redact → verify.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from redactron.detect.presidio_detector import Detection
from redactron.profile import Profile

log = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of processing a single PDF."""

    input_path: Path
    output_path: Path
    detections: list[Detection] = field(default_factory=list)
    verification_passed: bool | None = None
    survivors: int = 0


def run_pipeline(
    input_path: Path,
    output_path: Path,
    profile: Profile,
    *,
    score_threshold: float = 0.5,
    verify: bool = True,
) -> PipelineResult:
    """Run the full redaction pipeline for a single PDF.

    Profile-driven detectors run first and are authoritative.
    Presidio runs only when profile.detection.use_presidio is True.

    Args:
        input_path: Source PDF path.
        output_path: Destination path for the redacted PDF.
        profile: Loaded and validated Profile.
        score_threshold: Minimum score for Presidio detections.
        verify: Whether to run post-redaction verification.

    Returns:
        PipelineResult with detections and verification status.
    """
    from redactron.detect.account_detector import detect_custom_patterns
    from redactron.detect.address_detector import detect_addresses
    from redactron.detect.name_detector import detect_names
    from redactron.extract.text_layer import extract_text_layers, open_pdf
    from redactron.redact.engine import redact, save_redacted
    from redactron.redact.partial import detect_account_numbers

    doc = open_pdf(input_path)
    layers = extract_text_layers(doc)

    log.info("Loaded profile: %s (subject: %s)", profile.name, profile.subject.display_name)

    # --- Profile-driven detectors (always run, authoritative) ---
    profile_hits: list[Detection] = []
    profile_hits.extend(detect_names(layers, profile))
    profile_hits.extend(detect_addresses(layers, profile))
    profile_hits.extend(detect_account_numbers(doc, profile))
    profile_hits.extend(detect_custom_patterns(layers, profile))

    # --- Presidio (opt-in) ---
    presidio_hits: list[Detection] = []
    if profile.detection.use_presidio and profile.detection.presidio_entities:
        from redactron.detect.presidio_detector import detect as presidio_detect
        presidio_hits = presidio_detect(
            layers,
            entities=list(profile.detection.presidio_entities),
            score_threshold=score_threshold,
        )

    log.info(
        "Detectors enabled: profile=True, presidio=%s, entities=%s",
        profile.detection.use_presidio,
        profile.detection.presidio_entities if profile.detection.use_presidio else [],
    )

    # Merge: profile hits win on overlap (deduplicate by bbox+page)
    all_detections = _merge_detections(profile_hits, presidio_hits)

    log.info(
        "Detected %d spans (profile=%d, presidio=%d)",
        len(all_detections),
        len(profile_hits),
        len(presidio_hits),
    )

    redacted_doc = redact(doc, all_detections)
    save_redacted(redacted_doc, output_path)

    result = PipelineResult(
        input_path=input_path,
        output_path=output_path,
        detections=all_detections,
    )

    if verify:
        from redactron.verify.verifier import verify_redaction
        vr = verify_redaction(redacted_doc, all_detections)
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

    # Build set of (page_num, bbox) from profile hits for fast overlap check
    profile_keys: set[tuple[int, tuple[float, float, float, float]]] = {
        (d.page_num, d.bbox) for d in profile_hits
    }

    # Keep Presidio hits that don't overlap with any profile hit bbox
    filtered_presidio = [
        d for d in presidio_hits
        if not _overlaps_any(d, profile_keys)
    ]

    return profile_hits + filtered_presidio


def _overlaps_any(
    det: Detection,
    profile_keys: set[tuple[int, tuple[float, float, float, float]]],
) -> bool:
    """Return True if det's bbox overlaps any profile detection on the same page."""
    x0, y0, x1, y1 = det.bbox
    for page_num, (px0, py0, px1, py1) in profile_keys:
        if det.page_num != page_num:
            continue
        # Overlap if rectangles intersect
        if x0 < px1 and x1 > px0 and y0 < py1 and y1 > py0:
            return True
    return False
