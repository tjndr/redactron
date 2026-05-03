"""Tests for src/redactron/profile.py (BLD-7)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from redactron.errors import ProfileValidationError
from redactron.profile import (
    AccountNumber,
    CustomPattern,
    DetectionConfig,
    Profile,
    Subject,
    load_profile,
    save_profile,
)

SAMPLE_YAML = textwrap.dedent("""\
    version: 1
    name: default
    subject:
      display_name: "Tejinder Singh"
      aliases: ["Tejinder", "T. Singh", "Singh, Tejinder"]
      addresses:
        - "100 Phillip Street, San Jose, CA 95020, USA"
      phones: ["+1-408-555-1234"]
      emails: ["tejinder.singh@ieee.org"]
      ssns: ["xxx-xx-xxxx"]
      account_numbers:
        - value: "1234567890123456"
          preserve_last: 4
      custom_patterns:
        - name: patient_id
          regex: "PT-\\\\d{6}"
    detection:
      use_presidio: true
      presidio_entities:
        - PERSON
        - LOCATION
        - PHONE_NUMBER
        - EMAIL_ADDRESS
        - US_SSN
        - CREDIT_CARD
        - DATE_TIME
      fuzzy_match: true
      match_threshold: 0.85
      full_token_min_length: 2
      ocr_fallback: true
""")


def test_load_sample_profile(tmp_path: Path) -> None:
    """Loads the sample profile from kickoff_prompt without errors."""
    p = tmp_path / "profile.yaml"
    p.write_text(SAMPLE_YAML)
    profile = load_profile(p)
    assert profile.version == 1
    assert profile.subject.display_name == "Tejinder Singh"
    assert len(profile.subject.aliases) == 3
    assert profile.subject.account_numbers[0].preserve_last == 4
    assert profile.detection.match_threshold == 0.85


def test_load_minimal_profile(tmp_path: Path) -> None:
    """Minimal profile with only required fields loads successfully."""
    p = tmp_path / "profile.yaml"
    p.write_text("version: 1\nsubject:\n  display_name: Alice\n")
    profile = load_profile(p)
    assert profile.subject.display_name == "Alice"
    assert profile.detection.use_presidio is True  # default


def test_missing_file_raises(tmp_path: Path) -> None:
    """Missing file raises ProfileValidationError."""
    with pytest.raises(ProfileValidationError, match="not found"):
        load_profile(tmp_path / "nonexistent.yaml")


def test_invalid_yaml_raises(tmp_path: Path) -> None:
    """Invalid YAML raises ProfileValidationError."""
    p = tmp_path / "bad.yaml"
    p.write_text("version: 1\nsubject: [unclosed")
    with pytest.raises(ProfileValidationError, match="Invalid YAML"):
        load_profile(p)


def test_missing_display_name_raises(tmp_path: Path) -> None:
    """Missing display_name raises ProfileValidationError."""
    p = tmp_path / "profile.yaml"
    p.write_text("version: 1\nsubject:\n  aliases: []\n")
    with pytest.raises(ProfileValidationError):
        load_profile(p)


def test_empty_display_name_raises(tmp_path: Path) -> None:
    """Empty display_name raises ProfileValidationError."""
    p = tmp_path / "profile.yaml"
    p.write_text('version: 1\nsubject:\n  display_name: "  "\n')
    with pytest.raises(ProfileValidationError, match="display_name"):
        load_profile(p)


def test_unsupported_version_raises(tmp_path: Path) -> None:
    """Version != 1 raises ProfileValidationError."""
    p = tmp_path / "profile.yaml"
    p.write_text("version: 2\nsubject:\n  display_name: Alice\n")
    with pytest.raises(ProfileValidationError, match="version"):
        load_profile(p)


def test_invalid_threshold_raises() -> None:
    """match_threshold outside [0,1] raises ValidationError."""
    with pytest.raises(Exception):
        DetectionConfig(match_threshold=1.5)


def test_save_and_reload(tmp_path: Path) -> None:
    """save_profile + load_profile round-trips correctly."""
    profile = Profile(
        subject=Subject(
            display_name="Bob",
            aliases=["Robert"],
            account_numbers=[AccountNumber(value="9999888877776666", preserve_last=4)],
            custom_patterns=[CustomPattern(name="emp_id", regex=r"EMP-\d{5}")],
        )
    )
    path = tmp_path / "out.yaml"
    save_profile(profile, path)
    reloaded = load_profile(path)
    assert reloaded.subject.display_name == "Bob"
    assert reloaded.subject.aliases == ["Robert"]
    assert reloaded.subject.account_numbers[0].value == "9999888877776666"


def test_non_mapping_yaml_raises(tmp_path: Path) -> None:
    """YAML that is not a mapping raises ProfileValidationError."""
    p = tmp_path / "profile.yaml"
    p.write_text("- item1\n- item2\n")
    with pytest.raises(ProfileValidationError, match="mapping"):
        load_profile(p)
