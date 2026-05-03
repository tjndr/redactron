"""Post-redaction verifier: re-extract + re-detect to confirm no PII survived.

Strategy:
- Re-extract all text spans from the redacted document.
- Run the full profile-driven detector chain (names, addresses, account numbers,
  custom patterns, and optionally Presidio) against the re-extracted spans.
- Any detection returned by the re-run is a survivor.
- Partial-redaction survivors (preserve_last > 0) are filtered: if the surviving
  text is a suffix of the original that should have been preserved, it is not
  counted as a failure.

BLD-13 (M3.1)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import fitz

from redactron.detect.presidio_detector import Detection
from redactron.errors import VerificationError
from redactron.profile import Profile


@dataclass
class VerificationResult:
    """Result of a post-redaction verification pass."""

    passed: bool
    survivors: list[Detection] = field(default_factory=list)
    duration_ms: int = 0


def _is_preserved_suffix(survivor_text: str, original_detections: list[Detection]) -> bool:
    """Return True if survivor_text is only the preserved last-N suffix of a partial redaction.

    For account numbers with preserve_last > 0, the last N characters are intentionally
    left in the document. A re-detection of just those characters is expected and should
    not count as a failure.
    """
    s = survivor_text.strip()
    for det in original_detections:
        if det.preserve_last <= 0:
            continue
        # Strip non-digit chars from both sides for comparison
        original_digits = "".join(c for c in det.text if c.isdigit())
        survivor_digits = "".join(c for c in s if c.isdigit())
        if not survivor_digits:
            continue
        expected_suffix = original_digits[-det.preserve_last :]
        if survivor_digits == expected_suffix:
            return True
    return False


def verify_redaction(
    redacted_doc: fitz.Document,
    profile: Profile,
    original_detections: list[Detection] | None = None,
    score_threshold: float = 0.5,
    raise_on_survivors: bool = False,
) -> VerificationResult:
    """Re-extract and re-detect to confirm no PII survived redaction.

    Runs the full profile-driven detector chain against the redacted document.
    Any detection returned is a survivor (i.e., PII that was not fully redacted).

    Partial-redaction survivors (preserve_last > 0) are filtered out: if the
    surviving text is only the intentionally-preserved suffix, it is not a failure.

    Args:
        redacted_doc: The redacted fitz.Document to verify.
        profile: The profile used for the original redaction run.
        original_detections: Detections from the original run (used to filter
            partial-redaction survivors). Pass None to skip filtering.
        score_threshold: Minimum score for Presidio detections.
        raise_on_survivors: If True, raise VerificationError when survivors found.

    Returns:
        VerificationResult with passed=True if no survivors, False otherwise.

    Raises:
        VerificationError: If raise_on_survivors=True and survivors are found.
    """
    from redactron.detect.account_detector import detect_custom_patterns
    from redactron.detect.address_detector import detect_addresses
    from redactron.detect.name_detector import detect_names
    from redactron.extract.text_layer import extract_text_layers
    from redactron.redact.partial import detect_account_numbers

    t0 = time.monotonic()

    layers = extract_text_layers(redacted_doc)

    survivors: list[Detection] = []
    survivors.extend(detect_names(layers, profile))
    survivors.extend(detect_addresses(layers, profile))
    survivors.extend(detect_account_numbers(redacted_doc, profile))
    survivors.extend(detect_custom_patterns(layers, profile))

    if profile.detection.use_presidio and profile.detection.presidio_entities:
        from redactron.detect.presidio_detector import detect as presidio_detect
        survivors.extend(
            presidio_detect(
                layers,
                entities=list(profile.detection.presidio_entities),
                score_threshold=score_threshold,
            )
        )

    # Filter out intentionally-preserved partial-redaction suffixes
    if original_detections:
        survivors = [
            s for s in survivors
            if not _is_preserved_suffix(s.text, original_detections)
        ]

    duration_ms = int((time.monotonic() - t0) * 1000)
    passed = len(survivors) == 0

    result = VerificationResult(
        passed=passed,
        survivors=survivors,
        duration_ms=duration_ms,
    )

    if not passed and raise_on_survivors:
        survivor_texts = ", ".join(repr(s.text[:40]) for s in survivors[:5])
        raise VerificationError(
            f"{len(survivors)} PII item(s) survived redaction: {survivor_texts}"
        )

    return result
