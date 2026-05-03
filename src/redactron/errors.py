"""Typed exceptions for redactron.

All errors raised by the redaction pipeline are subclasses of RedactronError,
allowing the CLI to catch and format them uniformly.
"""


class RedactronError(Exception):
    """Base class for all redactron errors."""


class ProfileValidationError(RedactronError):
    """Raised when profile.yaml fails schema validation."""


class ExtractionError(RedactronError):
    """Raised when a PDF cannot be read or parsed."""


class RedactionError(RedactronError):
    """Raised when applying redaction annotations fails."""


class VerificationError(RedactronError):
    """Raised when PII survivors are detected after redaction."""


class NoTextLayerError(RedactronError):
    """Raised when a PDF has no extractable text layer (likely a scan)."""


class VaultError(RedactronError):
    """Raised on any vault crypto or format failure."""


class SecurityError(RedactronError):
    """Raised when a security invariant is violated (e.g. loose file permissions)."""
