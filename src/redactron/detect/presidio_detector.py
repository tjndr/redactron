"""Presidio-based PII detector.

Wraps Microsoft Presidio's AnalyzerEngine to detect PII entities in
extracted text spans, then maps results back to PDF bounding boxes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from presidio_analyzer import AnalyzerEngine, RecognizerResult

from redactron.extract.text_layer import TextLayer

# Default entities to detect when none are specified in the profile.
DEFAULT_ENTITIES: list[str] = [
    "PERSON",
    "LOCATION",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "US_SSN",
    "CREDIT_CARD",
    "DATE_TIME",
]


@dataclass(frozen=True, slots=True)
class Detection:
    """A single PII detection mapped to a PDF page and bounding box."""

    text: str
    entity_type: str
    score: float
    page_num: int
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1
    preserve_last: int = field(default=0)  # for partial redaction


@lru_cache(maxsize=1)
def _get_engine() -> AnalyzerEngine:
    """Return a cached AnalyzerEngine (expensive to initialise)."""
    return AnalyzerEngine()


def detect(
    layers: list[TextLayer],
    entities: list[str] | None = None,
    score_threshold: float = 0.5,
    language: str = "en",
) -> list[Detection]:
    """Detect PII entities in a list of TextLayer spans.

    Each TextLayer is analysed independently; Presidio results are mapped
    back to the layer's bounding box.

    Args:
        layers: Text spans extracted from a PDF page.
        entities: Entity types to detect. Defaults to DEFAULT_ENTITIES.
        score_threshold: Minimum confidence score to include a detection.
        language: Language code for the Presidio analyser.

    Returns:
        List of Detection objects, one per recognised PII span.
    """
    if entities is None:
        entities = DEFAULT_ENTITIES

    engine = _get_engine()
    detections: list[Detection] = []

    for layer in layers:
        if not layer.text:
            continue

        results: list[RecognizerResult] = engine.analyze(
            text=layer.text,
            entities=entities,
            language=language,
            score_threshold=score_threshold,
        )

        for result in results:
            matched_text = layer.text[result.start : result.end]
            detections.append(Detection(
                text=matched_text,
                entity_type=result.entity_type,
                score=result.score,
                page_num=layer.page_num,
                bbox=layer.bbox,
            ))

    return detections
