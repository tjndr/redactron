"""Account number detection with partial redaction (last-N preservation).

Detects account numbers from the profile in extracted text, computing
character-level bounding boxes so only the prefix is redacted while
the last N digits remain visible.
"""

from __future__ import annotations

import re

import fitz  # PyMuPDF

from redactron.detect.presidio_detector import Detection
from redactron.profile import AccountNumber, Profile

# Matches digit sequences with optional separators (hyphens, spaces, dots)
_DIGIT_SEP_RE = re.compile(r"[\d][\d\s\-\.]*[\d]")


def _digits_only(value: str) -> str:
    """Strip all non-digit characters from an account number string."""
    return re.sub(r"\D", "", value)


def _find_account_in_text(text: str, account: AccountNumber) -> list[tuple[int, int]]:
    """Return (start, end) char offsets of account number matches in text.

    Matches the account number with or without separators (hyphens/spaces).
    The digits must match exactly; separators in the text are ignored.

    Args:
        text: The text span to search.
        account: The account number to find.

    Returns:
        List of (start, end) offsets in *text* for each match.
    """
    target_digits = _digits_only(account.value)
    if not target_digits:
        return []

    matches: list[tuple[int, int]] = []
    for m in _DIGIT_SEP_RE.finditer(text):
        span_text = m.group()
        if _digits_only(span_text) == target_digits:
            matches.append((m.start(), m.end()))
    return matches


def _prefix_bbox(
    page: fitz.Page,
    full_text: str,
    match_start: int,
    match_end: int,
    preserve_last: int,
) -> tuple[float, float, float, float] | None:
    """Compute the bbox of the prefix portion to redact.

    Uses PyMuPDF rawdict to get per-character bboxes, then returns the
    union bbox of all characters that should be redacted (everything except
    the last *preserve_last* digit characters).

    Args:
        page: The PDF page containing the text.
        full_text: The full span text (used to locate chars in rawdict).
        match_start: Start offset of the account number in full_text.
        match_end: End offset of the account number in full_text.
        preserve_last: Number of trailing digit characters to preserve.

    Returns:
        Bounding box (x0, y0, x1, y1) of the prefix to redact, or None
        if character positions cannot be determined.
    """
    matched_text = full_text[match_start:match_end]
    # Identify which character positions (within matched_text) are digits
    digit_positions = [i for i, ch in enumerate(matched_text) if ch.isdigit()]
    if len(digit_positions) <= preserve_last:
        # Nothing to redact — all digits are preserved
        return None

    # The last preserve_last digit positions are kept; everything before is redacted
    if preserve_last > 0:
        redact_up_to_digit_idx = digit_positions[-(preserve_last + 1)]
    else:
        redact_up_to_digit_idx = digit_positions[-1]
    # Redact from start of match up to and including this character index
    redact_char_count = redact_up_to_digit_idx + 1  # chars within matched_text to redact

    # Walk rawdict to find character bboxes
    try:
        blocks = page.get_text("rawdict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    except Exception:
        return None

    # Collect all chars from the page in order
    page_chars: list[tuple[str, tuple[float, float, float, float]]] = []
    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                for ch in span.get("chars", []):
                    page_chars.append((ch["c"], tuple(ch["bbox"])))

    # Find the run of chars in page_chars that matches full_text
    # (simple substring search by character sequence)
    page_text = "".join(c for c, _ in page_chars)
    pos = page_text.find(full_text)
    if pos == -1:
        return None

    # Characters to redact: from match_start to match_start + redact_char_count
    redact_start = pos + match_start
    redact_end = redact_start + redact_char_count

    redact_chars = page_chars[redact_start:redact_end]
    if not redact_chars:
        return None

    x0 = min(b[0] for _, b in redact_chars)
    y0 = min(b[1] for _, b in redact_chars)
    x1 = max(b[2] for _, b in redact_chars)
    y1 = max(b[3] for _, b in redact_chars)
    return (x0, y0, x1, y1)


def detect_account_numbers(
    doc: fitz.Document,
    profile: Profile,
) -> list[Detection]:
    """Detect account numbers in a PDF and return partial-redaction Detections.

    For each account number in the profile, searches all text spans on each
    page. When preserve_last > 0, computes the bbox of only the prefix
    (digits to redact), leaving the last N digits visible.

    Args:
        doc: Open fitz.Document to search.
        profile: Loaded and validated Profile.

    Returns:
        List of Detection objects. Each has preserve_last set and bbox
        covering only the portion to be redacted.
    """
    accounts = profile.subject.account_numbers
    if not accounts:
        return []

    detections: list[Detection] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        try:
            blocks = page.get_text("rawdict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        except Exception:
            continue

        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    chars = span.get("chars", [])
                    if not chars:
                        continue
                    span_text = "".join(ch["c"] for ch in chars)
                    span_bbox: tuple[float, float, float, float] = (
                        min(ch["bbox"][0] for ch in chars),
                        min(ch["bbox"][1] for ch in chars),
                        max(ch["bbox"][2] for ch in chars),
                        max(ch["bbox"][3] for ch in chars),
                    )

                    for account in accounts:
                        for start, end in _find_account_in_text(span_text, account):
                            if account.preserve_last > 0:
                                bbox = _prefix_bbox(
                                    page, span_text, start, end, account.preserve_last
                                )
                                if bbox is None:
                                    # Fall back to full span bbox
                                    bbox = span_bbox
                            else:
                                bbox = span_bbox

                            detections.append(
                                Detection(
                                    text=span_text[start:end],
                                    entity_type="ACCOUNT_NUMBER",
                                    score=1.0,
                                    page_num=page_num,
                                    bbox=bbox,
                                    preserve_last=account.preserve_last,
                                )
                            )

    return detections


def mask_account_number(value: str, preserve_last: int = 4) -> str:
    """Return a masked representation of an account number string.

    Replaces all digit groups except the last *preserve_last* digits with 'X'.
    Separators (hyphens, spaces) are preserved in their original positions.

    Examples:
        mask_account_number("1234-5678-9012-3456", 4) -> "XXXX-XXXX-XXXX-3456"
        mask_account_number("1234567890123456", 4)    -> "XXXXXXXXXXXX3456"

    Args:
        value: The account number string (may contain separators).
        preserve_last: Number of trailing digits to keep visible.

    Returns:
        Masked string with leading digits replaced by 'X'.
    """
    digits = _digits_only(value)
    if not digits:
        return value

    keep_from = max(0, len(digits) - preserve_last)
    masked_digits = "X" * keep_from + digits[keep_from:]

    # Re-insert separators at their original positions
    result: list[str] = []
    digit_idx = 0
    for ch in value:
        if ch.isdigit():
            result.append(masked_digits[digit_idx])
            digit_idx += 1
        else:
            result.append(ch)
    return "".join(result)
