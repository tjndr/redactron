"""Tests for the SQLite audit log (BLD-14 / M3.2)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from redactron.audit.log import DocumentRecord, get_runs, log_run, migrate


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    return tmp_path / "test_audit.db"


class TestMigrate:
    def test_creates_tables(self, db: Path) -> None:
        conn = sqlite3.connect(str(db))
        migrate(conn)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "documents" in tables
        assert "subjects" in tables
        conn.close()

    def test_idempotent(self, db: Path) -> None:
        conn = sqlite3.connect(str(db))
        migrate(conn)
        migrate(conn)  # second call must not raise
        conn.close()


class TestLogRun:
    def test_inserts_row(self, db: Path) -> None:
        rec = DocumentRecord(file_hash="abc123", original_filename="test.pdf")
        rowid = log_run(rec, db=db)
        assert rowid == 1

    def test_second_insert_increments(self, db: Path) -> None:
        rec = DocumentRecord(file_hash="abc123")
        log_run(rec, db=db)
        rowid2 = log_run(rec, db=db)
        assert rowid2 == 2

    def test_all_fields_persisted(self, db: Path) -> None:
        ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        rec = DocumentRecord(
            file_hash="deadbeef",
            original_filename="in.pdf",
            output_filename="out.pdf",
            profile_name="default",
            subject_id="alice",
            pages_processed=5,
            items_detected=3,
            items_redacted=3,
            verification_passed=True,
            verification_survivors=[],
            duration_ms=1234,
            notes="test run",
            processed_at=ts,
        )
        log_run(rec, db=db)
        rows = get_runs(db=db)
        assert len(rows) == 1
        r = rows[0]
        assert r["file_hash"] == "deadbeef"
        assert r["pages_processed"] == 5
        assert r["items_detected"] == 3
        assert r["verification_passed"] == 1  # SQLite stores bool as int
        assert r["duration_ms"] == 1234
        assert r["notes"] == "test run"

    def test_subject_upsert_creates(self, db: Path) -> None:
        rec = DocumentRecord(file_hash="x", subject_id="bob")
        log_run(rec, db=db)
        conn = sqlite3.connect(str(db))
        row = conn.execute("SELECT * FROM subjects WHERE id='bob'").fetchone()
        conn.close()
        assert row is not None
        assert row[4] == 1  # document_count

    def test_subject_upsert_increments(self, db: Path) -> None:
        rec = DocumentRecord(file_hash="x", subject_id="carol")
        log_run(rec, db=db)
        log_run(rec, db=db)
        conn = sqlite3.connect(str(db))
        row = conn.execute("SELECT document_count FROM subjects WHERE id='carol'").fetchone()
        conn.close()
        assert row[0] == 2

    def test_no_subject_skips_subjects_table(self, db: Path) -> None:
        rec = DocumentRecord(file_hash="x", subject_id="")
        log_run(rec, db=db)
        conn = sqlite3.connect(str(db))
        count = conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
        conn.close()
        assert count == 0

    def test_verification_survivors_json(self, db: Path) -> None:
        rec = DocumentRecord(
            file_hash="x",
            verification_passed=False,
            verification_survivors=["Alice Sample", "alice@example.com"],
        )
        log_run(rec, db=db)
        import json
        rows = get_runs(db=db)
        survivors = json.loads(rows[0]["verification_survivors_json"])
        assert survivors == ["Alice Sample", "alice@example.com"]


class TestGetRuns:
    def test_empty_db_returns_empty(self, db: Path) -> None:
        assert get_runs(db=db) == []

    def test_missing_db_returns_empty(self, tmp_path: Path) -> None:
        assert get_runs(db=tmp_path / "nonexistent.db") == []

    def test_returns_most_recent_first(self, db: Path) -> None:
        for i in range(5):
            log_run(DocumentRecord(file_hash=f"hash{i}", notes=str(i)), db=db)
        rows = get_runs(db=db)
        assert rows[0]["notes"] == "4"
        assert rows[-1]["notes"] == "0"

    def test_limit(self, db: Path) -> None:
        for i in range(10):
            log_run(DocumentRecord(file_hash=f"h{i}"), db=db)
        rows = get_runs(limit=3, db=db)
        assert len(rows) == 3

    def test_filter_by_subject(self, db: Path) -> None:
        log_run(DocumentRecord(file_hash="a", subject_id="alice"), db=db)
        log_run(DocumentRecord(file_hash="b", subject_id="bob"), db=db)
        log_run(DocumentRecord(file_hash="c", subject_id="alice"), db=db)
        rows = get_runs(subject_id="alice", db=db)
        assert len(rows) == 2
        assert all(r["subject_id"] == "alice" for r in rows)

    def test_default_limit_20(self, db: Path) -> None:
        for i in range(25):
            log_run(DocumentRecord(file_hash=f"h{i}"), db=db)
        rows = get_runs(db=db)
        assert len(rows) == 20
