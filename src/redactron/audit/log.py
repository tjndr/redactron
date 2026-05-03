"""SQLite audit log for redactron.

Persists per-run records to ~/.redactron/audit.db (or REDACTRON_DB env var).
Schema migrations are idempotent: safe to run on an existing database.

BLD-14 (M3.2)
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


def _db_path() -> Path:
    """Return the audit DB path, respecting REDACTRON_DB env override."""
    env = os.environ.get("REDACTRON_DB")
    if env:
        return Path(env)
    return Path.home() / ".redactron" / "audit.db"


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DDL = """
CREATE TABLE IF NOT EXISTS documents (
    id                          INTEGER PRIMARY KEY,
    file_hash                   TEXT NOT NULL,
    original_filename           TEXT,
    output_filename             TEXT,
    processed_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    profile_name                TEXT,
    subject_id                  TEXT,
    pages_processed             INTEGER,
    items_detected              INTEGER,
    items_redacted              INTEGER,
    verification_passed         BOOLEAN,
    verification_survivors_json TEXT,
    duration_ms                 INTEGER,
    notes                       TEXT
);

CREATE TABLE IF NOT EXISTS subjects (
    id              TEXT PRIMARY KEY,
    display_name    TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at    TIMESTAMP,
    document_count  INTEGER DEFAULT 0
);
"""


def migrate(conn: sqlite3.Connection) -> None:
    """Apply schema migrations. Idempotent — safe on existing databases."""
    conn.executescript(_DDL)
    conn.commit()


@dataclass
class DocumentRecord:
    """One row in the documents audit table."""

    file_hash: str
    original_filename: str = ""
    output_filename: str = ""
    profile_name: str = ""
    subject_id: str = ""
    pages_processed: int = 0
    items_detected: int = 0
    items_redacted: int = 0
    verification_passed: bool | None = None
    verification_survivors: list[str] = field(default_factory=list)
    duration_ms: int = 0
    notes: str = ""
    processed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def log_run(record: DocumentRecord, db: Path | None = None) -> int:
    """Insert a DocumentRecord into the audit log and upsert subject stats.

    Args:
        record: The run record to persist.
        db: Optional path override (defaults to _db_path()).

    Returns:
        The rowid of the inserted documents row.
    """
    path = db or _db_path()
    conn = _connect(path)
    try:
        migrate(conn)
        survivors_json = json.dumps(record.verification_survivors)
        cur = conn.execute(
            """
            INSERT INTO documents (
                file_hash, original_filename, output_filename,
                processed_at, profile_name, subject_id,
                pages_processed, items_detected, items_redacted,
                verification_passed, verification_survivors_json,
                duration_ms, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.file_hash,
                record.original_filename,
                record.output_filename,
                record.processed_at.isoformat(),
                record.profile_name,
                record.subject_id,
                record.pages_processed,
                record.items_detected,
                record.items_redacted,
                record.verification_passed,
                survivors_json,
                record.duration_ms,
                record.notes,
            ),
        )
        rowid = cur.lastrowid or 0

        if record.subject_id:
            conn.execute(
                """
                INSERT INTO subjects (id, display_name, created_at, last_used_at, document_count)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(id) DO UPDATE SET
                    last_used_at = excluded.last_used_at,
                    document_count = document_count + 1
                """,
                (
                    record.subject_id,
                    record.subject_id,
                    record.processed_at.isoformat(),
                    record.processed_at.isoformat(),
                ),
            )

        conn.commit()
        return rowid
    finally:
        conn.close()


def get_runs(
    subject_id: str | None = None,
    limit: int = 20,
    db: Path | None = None,
) -> list[dict]:  # type: ignore[type-arg]
    """Fetch recent audit log entries.

    Args:
        subject_id: Filter by subject slug (None = all subjects).
        limit: Maximum rows to return.
        db: Optional path override.

    Returns:
        List of dicts with document row data.
    """
    path = db or _db_path()
    if not path.exists():
        return []
    conn = _connect(path)
    try:
        migrate(conn)
        if subject_id:
            rows = conn.execute(
                "SELECT * FROM documents WHERE subject_id = ? ORDER BY id DESC LIMIT ?",
                (subject_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def add_subject(subject_id: str, display_name: str, db: Path | None = None) -> None:
    """Create or update a subject entry.

    Args:
        subject_id: Unique slug identifier.
        display_name: Human-readable name.
        db: Optional path override.
    """
    path = db or _db_path()
    conn = _connect(path)
    try:
        migrate(conn)
        now = datetime.now(UTC).isoformat()
        conn.execute(
            """
            INSERT INTO subjects (id, display_name, created_at, last_used_at, document_count)
            VALUES (?, ?, ?, ?, 0)
            ON CONFLICT(id) DO UPDATE SET display_name = excluded.display_name
            """,
            (subject_id, display_name, now, now),
        )
        conn.commit()
    finally:
        conn.close()


def list_subjects(db: Path | None = None) -> list[dict]:  # type: ignore[type-arg]
    """Return all subjects ordered by last_used_at desc.

    Args:
        db: Optional path override.

    Returns:
        List of dicts with subject row data.
    """
    path = db or _db_path()
    if not path.exists():
        return []
    conn = _connect(path)
    try:
        migrate(conn)
        rows = conn.execute(
            "SELECT * FROM subjects ORDER BY last_used_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_subject(subject_id: str, db: Path | None = None) -> dict | None:  # type: ignore[type-arg]
    """Fetch a single subject by ID.

    Args:
        subject_id: The subject slug.
        db: Optional path override.

    Returns:
        Dict with subject data, or None if not found.
    """
    path = db or _db_path()
    if not path.exists():
        return None
    conn = _connect(path)
    try:
        migrate(conn)
        row = conn.execute(
            "SELECT * FROM subjects WHERE id = ?", (subject_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
