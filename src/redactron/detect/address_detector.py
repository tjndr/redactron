"""Address normalization and variant detection using usaddress + rapidfuzz.

Handles: abbreviated street types, ZIP+4, case-insensitive matching,
no-comma variants, and multi-line address spans.
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

_WHITESPACE_RE = re.compile(r"\s+")
# Strip ZIP+4 suffix for normalization (we keep it in the match but normalize without it)
_ZIP4_RE = re.compile(r"(\d{5})-\d{4}")


def _normalize_street_type(token: str) -> str:
    """Expand abbreviation to full form (lowercase)."""
    t = token.lower().rstrip(".")
    return _ABBR_TO_FULL.get(t, t)


def _strip_zip4(text: str) -> str:
    """Normalize ZIP+4 to 5-digit ZIP for comparison."""
    return _ZIP4_RE.sub(r"\1", text)


def _normalize_address(raw: str) -> str:
    """Return a normalized, lowercase address string.

    Parses with usaddress; falls back to simple whitespace-collapse on failure.
    Street-type tokens are expanded to their full form. ZIP+4 is reduced to ZIP5.
    """
    raw = _strip_zip4(raw)
    try:
        tagged, _ = usaddress.tag(raw)
    except usaddress.RepeatedLabelError:
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
    partial_ratio for substring/variant matching. Case-insensitive.
    Handles ZIP+4, abbreviated street types, and no-comma variants.

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
