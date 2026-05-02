"""redactron — local-only CLI for batch PII redaction in PDFs."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("redactron")
except PackageNotFoundError:  # running from source without install
    __version__ = "0.0.0.dev0"
