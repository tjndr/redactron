"""Address normalization and variant detection using usaddress + rapidfuzz.

Matching strategy (over-redaction safe):
- A PDF span must first parse as a valid address candidate (has StreetName
  component) before fuzzy comparison is attempted.
- Numeric tokens are NEVER fuzzy-matched in isolation.
- Uses fuzz.ratio (whole-string) not partial_ratio (substring).
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
_ZIP4_RE = re.compile(r"(\d{5})-\d{4}")

# Address candidate requires at least a street name component
_ADDRESS_REQUIRED_LABELS = frozenset({"StreetName", "StreetNamePreDirectional"})


def _is_numeric_token(s: str) -> bool:
    """Return True if s is purely numeric (digits, hyphens, spaces, dots)."""
    return s.replace("-", "").replace(" ", "").replace(".", "").isdigit()


def _normalize_street_type(token: str) -> str:
    t = token.lower().rstrip(".")
    return _ABBR_TO_FULL.get(t, t)


def _strip_zip4(text: str) -> str:
    return _ZIP4_RE.sub(r"\1", text)


def _normalize_address(raw: str) -> str:
    """Normalize address to lowercase with expanded street types and no ZIP+4."""
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


def _is_address_candidate(text: str) -> bool:
    """Return True only if text parses as a valid address (has a StreetName).

    This is the critical guard against over-redaction: numeric-only spans,
    single words, and short tokens are rejected before any fuzzy comparison.
    """
    # Fast reject: purely numeric or very short
    stripped = text.strip()
    if not stripped or len(stripped) < 5:
        return False
    if _is_numeric_token(stripped):
        return False

    try:
        tagged, _ = usaddress.tag(stripped)
    except usaddress.RepeatedLabelError:
        tagged = {}

    labels = set(tagged.keys()) if tagged else set()
    return bool(labels & _ADDRESS_REQUIRED_LABELS)


def detect_addresses(
    layers: list[TextLayer],
    profile: Profile,
) -> list[Detection]:
    """Detect address variants in text layers.

    Only spans that parse as valid address candidates (have a StreetName
    component) are compared against profile addresses. Numeric-only spans
    and short tokens are never matched.

    Uses fuzz.ratio (whole-string similarity) not partial_ratio, to prevent
    substring matches like '1' matching inside '91325'.
    """
    if not profile.subject.addresses:
        return []

    threshold = profile.detection.match_threshold * 100
    normalized_addresses = [_normalize_address(a) for a in profile.subject.addresses]

    detections: list[Detection] = []
    for layer in layers:
        if not layer.text:
            continue

        # Guard: only proceed if span looks like an address
        if not _is_address_candidate(layer.text):
            continue

        normalized_text = _normalize_address(layer.text)

        # Safety assertion: never fuzzy-match a purely numeric normalized form
        assert not _is_numeric_token(normalized_text), (
            f"Numeric token reached fuzzy match: {normalized_text!r}. "
            "Numeric tokens must use exact/regex match, not fuzzy."
        )

        for norm_addr in normalized_addresses:
            # partial_ratio is safe here because _is_address_candidate already
            # blocked all numeric-only and short spans. We're comparing two
            # address-like strings where substring matching is appropriate
            # (abbreviated forms, missing ZIP, etc.).
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
                break

    return detections
