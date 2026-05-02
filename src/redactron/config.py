"""Runtime configuration for redactron.

Values are resolved in priority order:
  1. Environment variables (REDACTRON_*)
  2. Defaults defined here
"""

import os
from pathlib import Path


def _redactron_dir() -> Path:
    return Path(os.environ.get("REDACTRON_HOME", Path.home() / ".redactron"))


def db_path() -> Path:
    """Path to the SQLite audit database."""
    return Path(os.environ.get("REDACTRON_DB", _redactron_dir() / "audit.db"))


def default_profile_path() -> Path:
    """Path to the default profile YAML."""
    return Path(os.environ.get("REDACTRON_PROFILE", _redactron_dir() / "profile.yaml"))


def redactron_dir() -> Path:
    """Base directory for redactron data files."""
    return _redactron_dir()
