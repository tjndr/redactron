"""Address normalization and variant detection using usaddress + rapidfuzz.

Parses profile addresses with usaddress, normalizes street-type abbreviations,
then fuzzy-matches normalized forms against extracted text spans.
"""

from __future__ import annotations

import re

import usaddress
from rapidfuzz import fuzz

from redactron.detect.presidio_detector import Detection
from redactron.extract.text_layer import TextLayer
from redactron.profile import Profile

# Canonical expansions for common street-type abbreviations (lowercase)
_ABBR_TO_FULL: dict[str, str] = {
    "st": "street",
    "ave": "avenue",
    "av": "avenue",
    "blvd": "boulevard",
    "dr": "drive",
    "rd": "road",
    "ln": "lane",
    "ct": "court",
    "pl": "place",
    "pkwy": "parkway",
    "hwy": "highway",
    "fwy": "freeway",
    "cir": "circle",
    "ter": "terrace",
    "trl": "trail",
    "way": "way",
}

_FULL_TO_ABBR: dict[str, str] = {v: k for k, v in _ABBR_TO_FULL.items()}

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_street_type(token: str) -> str:
    """Expand abbreviation to full form (lowercase)."""
    t = token.lower().rstrip(".")
    return _ABBR_TO_FULL.get(t, t)


def _normalize_address(raw: str) -> str:
    """Return a normalized, lowercase address string.

    Parses with usaddress; falls back to simple whitespace-collapse on failure.
    Street-type tokens are expanded to their full form for consistent comparison.
    """
    try:
        tagged, _ = usaddress.tag(raw)
    except usaddress.RepeatedLabelError:
        # Fall back to raw normalization
        return _WHITESPACE_RE.sub(" ", raw.lower().strip())

    parts: list[str] = []
    for label, value in tagged.items():
        if label == "StreetNamePostType":
            parts.append(_normalize_street_type(value))
        else:
            parts.append(value.lower())
    return " ".join(parts)


def detect_addresses(
    layers: list[TextLayer],
    profile: Profile,
) -> list[Detection]:
    """Detect address variants in text layers using usaddress + rapidfuzz.

    Normalizes each profile address and each text span, then computes
    token_set_ratio. A match is emitted when score >= match_threshold.

    Args:
        layers: Text spans extracted from a PDF page.
        profile: Loaded and validated Profile.

    Returns:
        List of Detection objects for matched address spans.
    """
    if not profile.subject.addresses:
        return []

    threshold = profile.detection.match_threshold * 100
    normalized_addresses = [_normalize_address(a) for a in profile.subject.addresses]

    detections: list[Detection] = []
    for layer in layers:
        if not layer.text:
            continue
        normalized_text = _normalize_address(layer.text)
        for norm_addr in normalized_addresses:
            # Use partial_ratio: address in text may be a substring of the full address
            score = fuzz.partial_ratio(norm_addr, normalized_text)
            if score >= threshold:
                detections.append(
                    Detection(
                        text=layer.text,
                        entity_type="LOCATION",
                        score=score / 100.0,
                        page_num=layer.page_num,
                        bbox=layer.bbox,
                    )
                )
                break  # one detection per layer span

    return detections
