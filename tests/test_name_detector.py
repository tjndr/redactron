"""Tests for src/redactron/detect/name_detector.py (BLD-8)."""

from __future__ import annotations

from redactron.detect.name_detector import detect_names
from redactron.extract.text_layer import TextLayer
from redactron.profile import DetectionConfig, Profile, Subject

BBOX = (0.0, 0.0, 100.0, 12.0)


def _layer(text: str, page: int = 0) -> TextLayer:
    return TextLayer(page_num=page, text=text, bbox=BBOX, block_type=0)


def _profile(
    display_name: str = "Tejinder Singh",
    aliases: list[str] | None = None,
    threshold: float = 0.85,
    min_len: int = 2,
) -> Profile:
    return Profile(
        subject=Subject(display_name=display_name, aliases=aliases or []),
        detection=DetectionConfig(match_threshold=threshold, full_token_min_length=min_len),
    )


def test_exact_display_name_matches() -> None:
    """Exact display_name match is detected."""
    layers = [_layer("Tejinder Singh")]
    result = detect_names(layers, _profile())
    assert len(result) == 1
    assert result[0].entity_type == "PERSON"
    assert result[0].score >= 0.85


def test_alias_matches() -> None:
    """Alias 'T. Singh' matches a span containing that text."""
    layers = [_layer("T. Singh")]
    result = detect_names(layers, _profile(aliases=["T. Singh", "Singh, Tejinder"]))
    assert len(result) == 1


def test_unrelated_text_no_match() -> None:
    """Unrelated text produces no detections."""
    layers = [_layer("Invoice #12345 dated 2024-01-01")]
    result = detect_names(layers, _profile())
    assert result == []


def test_short_token_alias_skipped() -> None:
    """Alias whose tokens are all below min_length is skipped entirely."""
    # alias "A B" — both tokens length 1, below min_len=2
    layers = [_layer("A B")]
    result = detect_names(layers, _profile(display_name="A B", min_len=2))
    assert result == []


def test_threshold_respected() -> None:
    """Score below threshold produces no detection."""
    layers = [_layer("John Doe")]
    result = detect_names(layers, _profile(threshold=0.99))
    assert result == []


def test_multiple_layers_multiple_matches() -> None:
    """Each matching layer produces one detection."""
    layers = [_layer("Tejinder Singh", page=0), _layer("Tejinder Singh", page=1)]
    result = detect_names(layers, _profile())
    assert len(result) == 2
    assert {d.page_num for d in result} == {0, 1}


def test_one_detection_per_span() -> None:
    """A span matching multiple aliases only produces one detection."""
    # "Tejinder Singh" matches both display_name and alias
    layers = [_layer("Tejinder Singh")]
    result = detect_names(layers, _profile(aliases=["Tejinder Singh"]))
    assert len(result) == 1


def test_empty_layers_returns_empty() -> None:
    """Empty layer list returns empty detections."""
    assert detect_names([], _profile()) == []


def test_empty_text_layer_skipped() -> None:
    """Layer with empty text is skipped."""
    layers = [TextLayer(page_num=0, text="", bbox=BBOX, block_type=0)]
    assert detect_names(layers, _profile()) == []


def test_score_in_range() -> None:
    """Detection score is in [0, 1]."""
    layers = [_layer("Tejinder Singh")]
    result = detect_names(layers, _profile())
    assert all(0.0 <= d.score <= 1.0 for d in result)


# --- STEP 4c robustness tests (BLD-30) ---
# Profile: display_name "Tejinder Singh", aliases ["Tejinder", "T. Singh", "Singh, Tejinder"]

def _tejinder_profile(threshold: float = 0.85) -> Profile:
    return Profile(
        subject=Subject(
            display_name="Tejinder Singh",
            aliases=["Tejinder", "T. Singh", "Singh, Tejinder"],
        ),
        detection=DetectionConfig(match_threshold=threshold, full_token_min_length=2),
    )


def test_full_name_matches() -> None:
    """'Tejinder Singh' is detected."""
    layers = [_layer("Tejinder Singh")]
    assert len(detect_names(layers, _tejinder_profile())) == 1


def test_alias_t_singh_matches() -> None:
    """Alias 'T. Singh' is detected."""
    layers = [_layer("T. Singh")]
    assert len(detect_names(layers, _tejinder_profile())) == 1


def test_alias_last_first_matches() -> None:
    """Alias 'Singh, Tejinder' is detected."""
    layers = [_layer("Singh, Tejinder")]
    assert len(detect_names(layers, _tejinder_profile())) == 1


def test_middle_initial_matches() -> None:
    """'Tejinder K. Singh' (middle initial) is detected."""
    layers = [_layer("Tejinder K. Singh")]
    assert len(detect_names(layers, _tejinder_profile())) == 1


def test_uppercase_matches() -> None:
    """'TEJINDER SINGH' (all caps) is detected."""
    layers = [_layer("TEJINDER SINGH")]
    assert len(detect_names(layers, _tejinder_profile())) == 1


def test_similar_but_different_not_matched() -> None:
    """'Tejinder Sharma' is NOT matched when using full-name aliases only."""
    # Use only full-name aliases (no single-token 'Tejinder' alias)
    profile = Profile(
        subject=Subject(
            display_name="Tejinder Singh",
            aliases=["T. Singh", "Singh, Tejinder"],  # no bare 'Tejinder'
        ),
        detection=DetectionConfig(match_threshold=0.92, full_token_min_length=2),
    )
    layers = [_layer("Tejinder Sharma")]
    result = detect_names(layers, profile)
    assert result == []


def test_corporate_context_suppressed() -> None:
    """'Singh Industries Inc.' is NOT matched (corporate entity)."""
    layers = [_layer("Singh Industries Inc.")]
    result = detect_names(layers, _tejinder_profile())
    assert result == []


def test_corporate_llc_suppressed() -> None:
    """'Tejinder Singh LLC' is NOT matched."""
    layers = [_layer("Tejinder Singh LLC")]
    result = detect_names(layers, _tejinder_profile())
    assert result == []
