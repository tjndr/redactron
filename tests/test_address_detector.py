"""Tests for src/redactron/detect/address_detector.py (BLD-9)."""

from __future__ import annotations

from redactron.detect.address_detector import _normalize_address, detect_addresses
from redactron.extract.text_layer import TextLayer
from redactron.profile import DetectionConfig, Profile, Subject

BBOX = (0.0, 0.0, 200.0, 12.0)


def _layer(text: str, page: int = 0) -> TextLayer:
    return TextLayer(page_num=page, text=text, bbox=BBOX, block_type=0)


def _profile(addresses: list[str], threshold: float = 0.85) -> Profile:
    return Profile(
        subject=Subject(display_name="Test User", addresses=addresses),
        detection=DetectionConfig(match_threshold=threshold),
    )


# --- normalization unit tests ---

def test_normalize_expands_street_abbr() -> None:
    """'St' expands to 'street' in normalized form."""
    norm = _normalize_address("100 Philip St, San Jose")
    assert "street" in norm


def test_normalize_expands_ave() -> None:
    """'Ave' expands to 'avenue'."""
    norm = _normalize_address("200 Main Ave")
    assert "avenue" in norm


def test_normalize_lowercases() -> None:
    """Normalized address is lowercase."""
    norm = _normalize_address("100 PHILLIP STREET")
    assert norm == norm.lower()


# --- detection tests ---

def test_exact_address_matches() -> None:
    """Exact address match is detected."""
    layers = [_layer("100 Phillip Street, San Jose, CA 95020")]
    result = detect_addresses(layers, _profile(["100 Phillip Street, San Jose, CA 95020"]))
    assert len(result) == 1
    assert result[0].entity_type == "LOCATION"


def test_abbreviated_variant_matches() -> None:
    """'100 Philip St, San Jose' matches '100 Phillip Street, San Jose, CA 95020'."""
    layers = [_layer("100 Philip St, San Jose")]
    result = detect_addresses(layers, _profile(["100 Phillip Street, San Jose, CA 95020"]))
    assert len(result) == 1


def test_unrelated_address_no_match() -> None:
    """Completely different address produces no detection."""
    layers = [_layer("999 Oak Avenue, New York, NY 10001")]
    result = detect_addresses(layers, _profile(["100 Phillip Street, San Jose, CA 95020"]))
    assert result == []


def test_no_addresses_in_profile_returns_empty() -> None:
    """Profile with no addresses returns empty list."""
    layers = [_layer("100 Phillip Street")]
    result = detect_addresses(layers, _profile([]))
    assert result == []


def test_empty_layers_returns_empty() -> None:
    """Empty layer list returns empty detections."""
    assert detect_addresses([], _profile(["100 Phillip Street"])) == []


def test_empty_text_layer_skipped() -> None:
    """Layer with empty text is skipped."""
    layers = [TextLayer(page_num=0, text="", bbox=BBOX, block_type=0)]
    assert detect_addresses(layers, _profile(["100 Phillip Street"])) == []


def test_score_in_range() -> None:
    """Detection score is in [0, 1]."""
    layers = [_layer("100 Phillip Street, San Jose, CA 95020")]
    result = detect_addresses(layers, _profile(["100 Phillip Street, San Jose, CA 95020"]))
    assert all(0.0 <= d.score <= 1.0 for d in result)


def test_one_detection_per_span() -> None:
    """A span matching multiple profile addresses only produces one detection."""
    addr = "100 Phillip Street, San Jose, CA 95020"
    layers = [_layer(addr)]
    result = detect_addresses(layers, _profile([addr, addr]))
    assert len(result) == 1


def test_multiple_pages() -> None:
    """Matching spans on different pages each produce a detection."""
    addr = "100 Phillip Street"
    layers = [_layer(addr, page=0), _layer(addr, page=2)]
    result = detect_addresses(layers, _profile([addr]))
    assert len(result) == 2
    assert {d.page_num for d in result} == {0, 2}


def test_normalize_fallback_on_ambiguous_address() -> None:
    """Normalization falls back gracefully on ambiguous/unparseable input."""
    from redactron.detect.address_detector import _normalize_address
    # Multiple addresses in one string triggers RepeatedLabelError in usaddress
    result = _normalize_address("100 Main St, 200 Oak Ave, 300 Pine Rd")
    assert isinstance(result, str)
    assert result == result.lower()
