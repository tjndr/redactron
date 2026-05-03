"""Name variant detector using rapidfuzz token-set ratio.

Matches subject name aliases against extracted text spans using fuzzy
matching, with case-insensitive comparison, middle-initial tolerance,
and corporate-entity suppression.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz

from redactron.detect.presidio_detector import Detection
from redactron.extract.text_layer import TextLayer
from redactron.profile import Profile

_WORD_RE = re.compile(r"\b\w+\b")

# Corporate suffixes that indicate a business entity, not a person
_CORPORATE_SUFFIXES = frozenset({
    "inc", "corp", "llc", "ltd", "co", "company", "corporation",
    "industries", "group", "associates", "partners", "holdings",
    "enterprises", "services", "solutions",
})


def _tokens(text: str) -> list[str]:
    """Return lowercase word tokens from text."""
    return _WORD_RE.findall(text.lower())


def _is_corporate_context(text: str) -> bool:
    """Return True if text looks like a corporate entity name."""
    tokens = _tokens(text)
    return bool(tokens and tokens[-1] in _CORPORATE_SUFFIXES)


def detect_names(
    layers: list[TextLayer],
    profile: Profile,
) -> list[Detection]:
    """Detect name aliases in text layers using rapidfuzz token_set_ratio.

    Matching is case-insensitive. Spans that look like corporate entity
    names (ending in Inc., Corp., LLC, etc.) are suppressed.

    Args:
        layers: Text spans extracted from a PDF page.
        profile: Loaded and validated Profile.

    Returns:
        List of Detection objects for matched name spans.
    """
    cfg = profile.detection
    threshold = cfg.match_threshold * 100  # rapidfuzz uses 0-100 scale
    min_len = cfg.full_token_min_length

    # Build candidate list: display_name + all aliases
    candidates: list[str] = [profile.subject.display_name] + list(profile.subject.aliases)
    # Only keep candidates that have at least one token >= min_len
    valid_candidates = [
        c for c in candidates if any(len(t) >= min_len for t in _tokens(c))
    ]

    detections: list[Detection] = []
    for layer in layers:
        if not layer.text:
            continue
        # Suppress corporate entity names
        if _is_corporate_context(layer.text):
            continue
        text_lower = layer.text.lower()
        for alias in valid_candidates:
            # Use max(token_set_ratio, partial_ratio) to catch names embedded
            # in longer sentences ("Prepared by Alice Sample.").
            # Require span to be at least half the alias length to prevent
            # single-char spans from matching via partial_ratio substring.
            if len(text_lower.strip()) < max(len(alias) * 0.5, 3):
                continue
            score = max(
                fuzz.token_set_ratio(alias.lower(), text_lower),
                fuzz.partial_ratio(alias.lower(), text_lower),
            )
            if score >= threshold:
                detections.append(
                    Detection(
                        text=layer.text,
                        entity_type="PERSON",
                        score=score / 100.0,
                        page_num=layer.page_num,
                        bbox=layer.bbox,
                    )
                )
                break  # one detection per layer span is enough

    return detections
