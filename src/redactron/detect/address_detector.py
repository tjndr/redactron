"""Address normalization and variant detection using usaddress + rapidfuzz.

Matching strategy (over-redaction safe):
- A PDF span must first parse as a valid address candidate (has StreetName)
  before fuzzy comparison is attempted.
- Numeric tokens are NEVER fuzzy-matched in isolation.
- Multi-line addresses are bridged: a street line looks forward up to
  address_line_bridge_window subsequent lines for a city/state/zip
  continuation, stopping at non-address prose.
"""

from __future__ import annotations

import re

import usaddress
from rapidfuzz import fuzz

from redactron.detect.presidio_detector import Detection
from redactron.extract.text_layer import TextLayer
from redactron.profile import Profile

_ABBR_TO_FULL: dict[str, str] = {
    "st": "street", "ave": "avenue", "av": "avenue", "blvd": "boulevard",
    "dr": "drive", "rd": "road", "ln": "lane", "ct": "court", "pl": "place",
    "pkwy": "parkway", "hwy": "highway", "fwy": "freeway", "cir": "circle",
    "ter": "terrace", "trl": "trail", "way": "way",
}

_WHITESPACE_RE = re.compile(r"\s+")
_ZIP4_RE = re.compile(r"(\d{5})-\d{4}")
_ZIP_RE = re.compile(r"\b\d{5}(?:-\d{4})?\b")

# 2-letter US state abbreviations
_US_STATES = frozenset({
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN",
    "IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV",
    "NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN",
    "TX","UT","VT","VA","WA","WV","WI","WY","DC",
})

# Occupancy keywords that indicate a mid-address continuation line
_OCCUPANCY_WORDS = frozenset({"suite", "apt", "apartment", "unit", "ste", "fl", "floor"})

# Address candidate requires at least a street name component
_ADDRESS_REQUIRED_LABELS = frozenset({"StreetName", "StreetNamePreDirectional"})


def _is_numeric_token(s: str) -> bool:
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

    Critical guard against over-redaction: numeric-only spans, single words,
    and short tokens are rejected before any fuzzy comparison.
    """
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


def _is_address_continuation(text: str) -> bool:
    """Return True if text looks like a city/state/zip or occupancy continuation.

    Used for multi-line bridging: after a street line, look forward for lines
    that continue the address. Stop at prose/non-address content.
    """
    stripped = text.strip()
    if not stripped:
        return True  # empty lines are transparent (skip over them)

    tokens_upper = stripped.upper().split()

    # Has a ZIP code → strong signal
    if _ZIP_RE.search(stripped):
        return True

    # Has a US state abbreviation → likely city/state line
    if any(t.rstrip(",") in _US_STATES for t in tokens_upper):
        return True

    # Occupancy line (Suite 400, Apt 2B, etc.)
    first = stripped.lower().split()[0].rstrip(".")
    if first in _OCCUPANCY_WORDS:
        return True

    return False


def _is_prose_line(text: str) -> bool:
    """Return True if text looks like prose (not an address component).

    Used to stop bridging when non-address content is encountered.
    """
    stripped = text.strip()
    if not stripped:
        return False  # empty lines don't count as prose

    # More than 6 tokens and no ZIP/state → likely prose
    tokens = stripped.split()
    if len(tokens) > 6:
        has_zip = bool(_ZIP_RE.search(stripped))
        has_state = any(t.rstrip(",").upper() in _US_STATES for t in tokens)
        if not has_zip and not has_state:
            return True

    return False


def _build_address_groups(
    layers: list[TextLayer],
    bridge_window: int,
) -> list[list[TextLayer]]:
    """Group layers into address candidate groups using multi-line bridging.

    For each layer that is a street-line candidate, look forward up to
    bridge_window subsequent layers for continuation lines (city/state/zip,
    occupancy). Stop bridging if a prose line is encountered.

    Returns a list of groups; each group is a list of TextLayer objects
    that together form one address candidate.
    """
    groups: list[list[TextLayer]] = []
    used: set[int] = set()

    for i, layer in enumerate(layers):
        if i in used:
            continue
        if not _is_address_candidate(layer.text):
            continue

        # Start a new group with this street line
        group: list[TextLayer] = [layer]
        used.add(i)

        # Look forward for continuation lines
        lookahead = 0
        j = i + 1
        while j < len(layers) and lookahead < bridge_window:
            next_layer = layers[j]
            j += 1

            # Empty line: transparent, don't count against window
            if not next_layer.text.strip():
                group.append(next_layer)
                continue

            # Prose line: stop bridging
            if _is_prose_line(next_layer.text):
                break

            # Address continuation: add to group
            if _is_address_continuation(next_layer.text):
                group.append(next_layer)
                used.add(j - 1)
                lookahead += 1
            else:
                # Not continuation, not prose — stop
                break

        groups.append(group)

    return groups


def detect_addresses(
    layers: list[TextLayer],
    profile: Profile,
) -> list[Detection]:
    """Detect address variants in text layers with multi-line bridging.

    Only spans that parse as valid address candidates (have a StreetName
    component) are compared against profile addresses. Numeric-only spans
    and short tokens are never matched.

    Multi-line bridging: a street line looks forward up to
    profile.detection.address_line_bridge_window (default 3) subsequent
    lines for city/state/zip continuations, stopping at prose content.
    """
    if not profile.subject.addresses:
        return []

    threshold = profile.detection.match_threshold * 100
    normalized_addresses = [_normalize_address(a) for a in profile.subject.addresses]
    bridge_window = getattr(profile.detection, "address_line_bridge_window", 3)

    # Build address candidate groups (handles multi-line)
    groups = _build_address_groups(layers, bridge_window)

    detections: list[Detection] = []
    for group in groups:
        # Combine non-empty lines for matching
        combined_text = " ".join(lay.text for lay in group if lay.text.strip())
        normalized_text = _normalize_address(combined_text)

        assert not _is_numeric_token(normalized_text), (
            f"Numeric token reached fuzzy match: {normalized_text!r}. "
            "Numeric tokens must use exact/regex match, not fuzzy."
        )

        for norm_addr in normalized_addresses:
            score = fuzz.partial_ratio(norm_addr, normalized_text)
            if score >= threshold:
                # Emit one Detection per non-empty line (separate bboxes)
                for layer in group:
                    if layer.text.strip():
                        detections.append(Detection(
                            text=layer.text,
                            entity_type="LOCATION",
                            score=score / 100.0,
                            page_num=layer.page_num,
                            bbox=layer.bbox,
                        ))
                break

    return detections
