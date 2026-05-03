"""Custom regex pattern detector from profile.

Compiles and applies user-defined regex patterns against extracted text spans.
"""

from __future__ import annotations

import re

from redactron.detect.presidio_detector import Detection
from redactron.extract.text_layer import TextLayer
from redactron.profile import Profile


def detect_custom_patterns(
    layers: list[TextLayer],
    profile: Profile,
) -> list[Detection]:
    """Detect custom regex patterns defined in the profile.

    Each pattern in profile.subject.custom_patterns is compiled and searched
    against every text span. The pattern name is used as entity_type.

    Args:
        layers: Text spans extracted from a PDF page.
        profile: Loaded and validated Profile.

    Returns:
        List of Detection objects for each regex match.
    """
    patterns = profile.subject.custom_patterns
    if not patterns:
        return []

    compiled = [(p.name, re.compile(p.regex)) for p in patterns]
    detections: list[Detection] = []

    for layer in layers:
        if not layer.text:
            continue
        for name, rx in compiled:
            for m in rx.finditer(layer.text):
                detections.append(
                    Detection(
                        text=m.group(),
                        entity_type=name,
                        score=1.0,
                        page_num=layer.page_num,
                        bbox=layer.bbox,
                    )
                )

    return detections
