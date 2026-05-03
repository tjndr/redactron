"""Tests for src/redactron/detect/account_detector.py (BLD-11)."""

from __future__ import annotations

from pathlib import Path

import pytest

from redactron.detect.account_detector import detect_custom_patterns
from redactron.errors import ProfileValidationError
from redactron.extract.text_layer import TextLayer
from redactron.profile import CustomPattern, DetectionConfig, Profile, Subject, load_profile

BBOX = (0.0, 0.0, 200.0, 12.0)
PT_PATTERN = CustomPattern(name="patient_id", regex=r"PT-\d{6}")


def _layer(text: str, page: int = 0) -> TextLayer:
    return TextLayer(page_num=page, text=text, bbox=BBOX, block_type=0)


def _profile(patterns: list[CustomPattern]) -> Profile:
    return Profile(
        subject=Subject(display_name="Test", custom_patterns=patterns),
        detection=DetectionConfig(),
    )


def test_patient_id_matches() -> None:
    """PT-123456 matches pattern PT-\\d{6}."""
    layers = [_layer("Patient: PT-123456 admitted")]
    result = detect_custom_patterns(layers, _profile([PT_PATTERN]))
    assert len(result) == 1
    assert result[0].text == "PT-123456"
    assert result[0].entity_type == "patient_id"
    assert result[0].score == 1.0


def test_no_match_returns_empty() -> None:
    """Text without matching pattern returns empty list."""
    layers = [_layer("No patient ID here")]
    result = detect_custom_patterns(layers, _profile([PT_PATTERN]))
    assert result == []


def test_multiple_matches_in_one_span() -> None:
    """Multiple matches in one span each produce a detection."""
    layers = [_layer("PT-000001 and PT-999999")]
    pid_pattern = CustomPattern(name="pid", regex=r"PT-\d{6}")
    result = detect_custom_patterns(layers, _profile([pid_pattern]))
    assert len(result) == 2
    assert {d.text for d in result} == {"PT-000001", "PT-999999"}


def test_multiple_patterns() -> None:
    """Multiple patterns each match independently."""
    layers = [_layer("PT-123456 EMP-00042")]
    patterns = [
        CustomPattern(name="patient_id", regex=r"PT-\d{6}"),
        CustomPattern(name="emp_id", regex=r"EMP-\d{5}"),
    ]
    result = detect_custom_patterns(layers, _profile(patterns))
    assert len(result) == 2
    assert {d.entity_type for d in result} == {"patient_id", "emp_id"}


def test_no_patterns_returns_empty() -> None:
    """Profile with no custom patterns returns empty list."""
    layers = [_layer("PT-123456")]
    assert detect_custom_patterns(layers, _profile([])) == []


def test_empty_layers_returns_empty() -> None:
    """Empty layer list returns empty detections."""
    assert detect_custom_patterns([], _profile([CustomPattern(name="p", regex=r"\d+")])) == []


def test_empty_text_layer_skipped() -> None:
    """Layer with empty text is skipped."""
    layers = [TextLayer(page_num=0, text="", bbox=BBOX, block_type=0)]
    assert detect_custom_patterns(layers, _profile([CustomPattern(name="p", regex=r"\d+")])) == []


def test_page_num_preserved() -> None:
    """Detection page_num matches the layer's page_num."""
    layers = [_layer("PT-123456", page=3)]
    pid_pattern = CustomPattern(name="pid", regex=r"PT-\d{6}")
    result = detect_custom_patterns(layers, _profile([pid_pattern]))
    assert result[0].page_num == 3


def test_invalid_regex_raises_at_pattern_creation() -> None:
    """Invalid regex raises ValidationError at CustomPattern creation."""
    with pytest.raises(Exception, match="[Ii]nvalid regex|[Vv]alid"):
        CustomPattern(name="bad", regex=r"[unclosed")


def test_invalid_regex_in_yaml_raises_profile_validation_error(tmp_path: Path) -> None:
    """Invalid regex in profile YAML raises ProfileValidationError."""
    p = tmp_path / "profile.yaml"
    p.write_text(
        "version: 1\nsubject:\n  display_name: Test\n  custom_patterns:\n"
        "    - name: bad\n      regex: '[unclosed'\n"
    )
    with pytest.raises(ProfileValidationError):
        load_profile(p)
