"""Post-redaction verifier — stub for M1.6 CLI wiring.

Full implementation in BLD-13 (M3.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import fitz

from redactron.detect.presidio_detector import Detection


@dataclass
class VerificationResult:
    """Result of a post-redaction verification pass."""

    passed: bool
    survivors: list[Detection] = field(default_factory=list)
    duration_ms: int = 0


def verify_redaction(
    redacted_doc: fitz.Document,
    original_detections: list[Detection],
) -> VerificationResult:
    """Re-extract and re-detect to confirm no PII survived redaction.

    Stub implementation: always returns passed=True.
    Full implementation in BLD-13.
    """
    return VerificationResult(passed=True)
