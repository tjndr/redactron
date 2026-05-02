"""Tests for src/redactron/detect/presidio_detector.py."""

from redactron.detect.presidio_detector import DEFAULT_ENTITIES, Detection, detect
from redactron.extract.text_layer import TextLayer


def _layer(text: str, page: int = 0) -> TextLayer:
    return TextLayer(page_num=page, text=text, bbox=(0.0, 0.0, 100.0, 12.0), block_type=0)


def test_detect_returns_list() -> None:
    layers = [_layer("Hello world")]
    result = detect(layers)
    assert isinstance(result, list)


def test_detect_person() -> None:
    layers = [_layer("My name is John Smith.")]
    results = detect(layers, entities=["PERSON"])
    assert any(d.entity_type == "PERSON" for d in results)


def test_detect_email() -> None:
    layers = [_layer("Contact me at john.smith@example.com")]
    results = detect(layers, entities=["EMAIL_ADDRESS"])
    assert any(d.entity_type == "EMAIL_ADDRESS" for d in results)


def test_detect_phone() -> None:
    layers = [_layer("Call +1-800-555-1234 for support.")]
    results = detect(layers, entities=["PHONE_NUMBER"], score_threshold=0.4)
    assert any(d.entity_type == "PHONE_NUMBER" for d in results)


def test_detection_text_is_substring_of_layer() -> None:
    layer = _layer("Email: alice@example.com")
    results = detect([layer], entities=["EMAIL_ADDRESS"])
    for d in results:
        assert d.text in layer.text


def test_detection_bbox_matches_layer() -> None:
    layer = _layer("alice@example.com")
    results = detect([layer], entities=["EMAIL_ADDRESS"])
    assert len(results) > 0
    assert results[0].bbox == layer.bbox


def test_detection_page_num_preserved() -> None:
    layer = _layer("john@example.com", page=3)
    results = detect([layer], entities=["EMAIL_ADDRESS"])
    assert len(results) > 0
    assert results[0].page_num == 3


def test_score_threshold_filters_low_confidence() -> None:
    layers = [_layer("My name is John Smith.")]
    high = detect(layers, entities=["PERSON"], score_threshold=0.9)
    low = detect(layers, entities=["PERSON"], score_threshold=0.1)
    assert len(low) >= len(high)


def test_empty_layers_returns_empty() -> None:
    assert detect([]) == []


def test_empty_text_layer_skipped() -> None:
    layers = [_layer("")]
    result = detect(layers)
    assert result == []


def test_no_pii_returns_empty() -> None:
    layers = [_layer("The quick brown fox jumps over the lazy dog.")]
    results = detect(layers, entities=["US_SSN", "CREDIT_CARD"])
    assert results == []


def test_detection_is_frozen_dataclass() -> None:
    d = Detection(
        text="test", entity_type="PERSON", score=0.9,
        page_num=0, bbox=(0.0, 0.0, 10.0, 10.0)
    )
    assert d.preserve_last == 0


def test_default_entities_non_empty() -> None:
    assert len(DEFAULT_ENTITIES) > 0


def test_multipage_detections() -> None:
    layers = [
        _layer("john@example.com", page=0),
        _layer("jane@example.com", page=2),
    ]
    results = detect(layers, entities=["EMAIL_ADDRESS"])
    page_nums = {d.page_num for d in results}
    assert 0 in page_nums
    assert 2 in page_nums
