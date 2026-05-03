"""Name variant detector using rapidfuzz token-set ratio.

Matching strategy:
- Multi-token aliases (e.g. "Tejinder Singh"): fuzzy match using
  max(token_set_ratio, partial_ratio) to catch names in longer sentences.
- Single-token aliases (e.g. "Singh"): exact word-boundary match only.
  Fuzzy matching single tokens causes catastrophic over-matching in
  academic papers, legal documents, etc.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz

from redactron.detect.presidio_detector import Detection
from redactron.extract.text_layer import TextLayer
from redactron.profile import Profile

_WORD_RE = re.compile(r"\b\w+\b")

_CORPORATE_SUFFIXES = frozenset({
    "inc", "corp", "llc", "ltd", "co", "company", "corporation",
    "industries", "group", "associates", "partners", "holdings",
    "enterprises", "services", "solutions",
})


def _tokens(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _is_corporate_context(text: str) -> bool:
    tokens = _tokens(text)
    return bool(tokens and tokens[-1] in _CORPORATE_SUFFIXES)


def detect_names(
    layers: list[TextLayer],
    profile: Profile,
) -> list[Detection]:
    """Detect name aliases in text layers.

    Multi-token aliases use fuzzy matching (catches names in sentences).
    Single-token aliases use exact word-boundary matching only (prevents
    over-matching in academic/legal documents with common surnames).
    """
    cfg = profile.detection
    threshold = cfg.match_threshold * 100
    min_len = cfg.full_token_min_length

    candidates: list[str] = [profile.subject.display_name] + list(profile.subject.aliases)
    valid_candidates = [
        c for c in candidates if any(len(t) >= min_len for t in _tokens(c))
    ]

    # Pre-compile exact patterns for single-token aliases
    single_token_patterns: dict[str, re.Pattern[str]] = {}
    multi_token_aliases: list[str] = []
    for alias in valid_candidates:
        toks = _tokens(alias)
        if len(toks) == 1:
            single_token_patterns[alias] = re.compile(
                r"\b" + re.escape(alias) + r"\b", re.IGNORECASE
            )
        else:
            multi_token_aliases.append(alias)

    detections: list[Detection] = []
    for layer in layers:
        if not layer.text:
            continue
        if _is_corporate_context(layer.text):
            continue
        text_lower = layer.text.lower()

        matched = False

        # Multi-token: fuzzy match (catches "Prepared by Alice Sample.")
        for alias in multi_token_aliases:
            if len(text_lower.strip()) < max(len(alias) * 0.5, 3):
                continue
            score = max(
                fuzz.token_set_ratio(alias.lower(), text_lower),
                fuzz.partial_ratio(alias.lower(), text_lower),
            )
            if score >= threshold:
                matched = True
                break

        # Single-token: exact word boundary only
        if not matched:
            for alias, pattern in single_token_patterns.items():
                if pattern.search(layer.text):
                    matched = True
                    break

        if matched:
            detections.append(Detection(
                text=layer.text,
                entity_type="PERSON",
                score=1.0,
                page_num=layer.page_num,
                bbox=layer.bbox,
            ))

    return detections
