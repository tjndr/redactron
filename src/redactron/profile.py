"""Profile schema (Pydantic v2) and YAML loader for redactron.

The profile.yaml file describes the subject's PII and detection settings.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from redactron.errors import ProfileValidationError


class AccountNumber(BaseModel):
    """A single account number with optional last-N preservation."""

    value: str
    preserve_last: Annotated[int, Field(ge=0, le=16)] = 4


class CustomPattern(BaseModel):
    """A named regex pattern to redact."""

    name: str
    regex: str

    @field_validator("regex")
    @classmethod
    def regex_is_valid(cls, v: str) -> str:
        """Ensure the regex compiles without error."""
        try:
            re.compile(v)
        except re.error as exc:
            raise ValueError(f"Invalid regex {v!r}: {exc}") from exc
        return v


class Subject(BaseModel):
    """PII belonging to the subject of redaction."""

    display_name: str
    aliases: list[str] = Field(default_factory=list)
    addresses: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)
    ssns: list[str] = Field(default_factory=list)
    account_numbers: list[AccountNumber] = Field(default_factory=list)
    custom_patterns: list[CustomPattern] = Field(default_factory=list)

    @field_validator("display_name")
    @classmethod
    def display_name_not_empty(cls, v: str) -> str:
        """Ensure display_name is non-empty."""
        if not v.strip():
            raise ValueError("display_name must not be empty")
        return v


class DetectionConfig(BaseModel):
    """Detection settings."""

    use_presidio: bool = False  # profile-only by default
    presidio_entities: list[str] = Field(default_factory=list)
    fuzzy_match: bool = True
    match_threshold: Annotated[float, Field(ge=0.0, le=1.0)] = 0.85
    full_token_min_length: Annotated[int, Field(ge=1)] = 2
    ocr_fallback: bool = False


class Profile(BaseModel):
    """Top-level profile schema."""

    version: Annotated[int, Field(ge=1)] = 1
    name: str = "default"
    subject: Subject
    detection: DetectionConfig = Field(default_factory=DetectionConfig)

    @model_validator(mode="after")
    def validate_version(self) -> Profile:
        """Only version 1 is supported in v1."""
        if self.version != 1:
            raise ValueError(
                f"Unsupported profile version: {self.version}. Only version 1 is supported."
            )
        return self


def load_profile(path: Path | str) -> Profile:
    """Load and validate a profile YAML file.

    Accepts both Path and str arguments.

    Args:
        path: Path to the profile.yaml file (str or Path).

    Returns:
        Validated Profile instance.

    Raises:
        ProfileValidationError: If the file is missing, invalid YAML, or fails schema validation.
    """
    path = Path(path)
    if not path.exists():
        raise ProfileValidationError(
            f"Profile not found: {path}\n"
            "Run `redactron init` to create a default profile."
        )
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ProfileValidationError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ProfileValidationError(f"Profile must be a YAML mapping, got {type(raw).__name__}")
    try:
        return Profile.model_validate(raw)
    except Exception as exc:
        raise ProfileValidationError(f"Profile validation failed: {exc}") from exc


def save_profile(profile: Profile, path: Path) -> None:
    """Serialize a Profile to YAML and write it to disk.

    Args:
        profile: The Profile instance to save.
        path: Destination path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.dump(profile.model_dump(), default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
