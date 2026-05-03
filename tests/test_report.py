"""Tests for the Markdown/JSON report generator (BLD-16 / M3.4)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from redactron.audit.log import DocumentRecord
from redactron.report.markdown import render_from_db, render_json, render_markdown, write_reports


def _record(**kwargs) -> DocumentRecord:  # type: ignore[no-untyped-def]
    defaults = dict(
        file_hash="abc",
        original_filename="in.pdf",
        output_filename="in_redacted.pdf",
        profile_name="default",
        subject_id="alice",
        pages_processed=3,
        items_detected=5,
        items_redacted=5,
        verification_passed=True,
        verification_survivors=[],
        duration_ms=420,
        processed_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
    )
    defaults.update(kwargs)
    return DocumentRecord(**defaults)


class TestRenderMarkdown:
    def test_contains_filename(self) -> None:
        md = render_markdown(_record())
        assert "in.pdf" in md

    def test_passed_verification(self) -> None:
        md = render_markdown(_record(verification_passed=True))
        assert "✅ Passed" in md

    def test_failed_verification(self) -> None:
        md = render_markdown(_record(
            verification_passed=False,
            verification_survivors=["Alice Sample", "alice@x.com"],
        ))
        assert "❌ Failed" in md
        assert "2 PII item(s)" in md

    def test_survivors_section(self) -> None:
        md = render_markdown(_record(
            verification_passed=False,
            verification_survivors=["Alice Sample"],
        ))
        assert "## Survivors" in md
        assert "Alice Sample" in md

    def test_skipped_verification(self) -> None:
        md = render_markdown(_record(verification_passed=None))
        assert "N/A" in md

    def test_no_subject_line_when_empty(self) -> None:
        md = render_markdown(_record(subject_id=""))
        assert "**Subject:**" not in md

    def test_subject_line_present(self) -> None:
        md = render_markdown(_record(subject_id="alice"))
        assert "**Subject:** alice" in md

    def test_metrics_table(self) -> None:
        md = render_markdown(_record(pages_processed=7, items_detected=4))
        assert "7" in md
        assert "4" in md


class TestRenderJson:
    def test_valid_json(self) -> None:
        j = render_json(_record())
        data = json.loads(j)
        assert data["original_filename"] == "in.pdf"
        assert data["items_detected"] == 5
        assert data["verification_passed"] is True

    def test_survivors_list(self) -> None:
        j = render_json(_record(verification_survivors=["x", "y"]))
        data = json.loads(j)
        assert data["verification_survivors"] == ["x", "y"]


class TestWriteReports:
    def test_creates_md_and_json(self, tmp_path: Path) -> None:
        pdf = tmp_path / "out_redacted.pdf"
        pdf.write_bytes(b"fake")
        md_path, json_path = write_reports(_record(), pdf)
        assert md_path.exists()
        assert json_path.exists()
        assert md_path.suffix == ".md"
        assert json_path.suffix == ".json"

    def test_md_content(self, tmp_path: Path) -> None:
        pdf = tmp_path / "out_redacted.pdf"
        pdf.write_bytes(b"fake")
        md_path, _ = write_reports(_record(), pdf)
        content = md_path.read_text()
        assert "Redactron Report" in content

    def test_json_parseable(self, tmp_path: Path) -> None:
        pdf = tmp_path / "out_redacted.pdf"
        pdf.write_bytes(b"fake")
        _, json_path = write_reports(_record(), pdf)
        data = json.loads(json_path.read_text())
        assert "original_filename" in data


class TestRenderFromDb:
    def test_renders_from_db_row(self) -> None:
        row = {
            "id": 1,
            "file_hash": "abc",
            "original_filename": "in.pdf",
            "output_filename": "out.pdf",
            "profile_name": "default",
            "subject_id": "alice",
            "pages_processed": 2,
            "items_detected": 3,
            "items_redacted": 3,
            "verification_passed": 1,
            "verification_survivors_json": "[]",
            "duration_ms": 100,
            "notes": "",
            "processed_at": "2026-01-01T12:00:00+00:00",
        }
        md = render_from_db(row)
        assert "in.pdf" in md
        assert "✅ Passed" in md

    def test_failed_from_db_row(self) -> None:
        row = {
            "id": 2,
            "file_hash": "xyz",
            "original_filename": "doc.pdf",
            "output_filename": "doc_redacted.pdf",
            "profile_name": "default",
            "subject_id": "",
            "pages_processed": 1,
            "items_detected": 2,
            "items_redacted": 1,
            "verification_passed": 0,
            "verification_survivors_json": '["Alice Sample"]',
            "duration_ms": 200,
            "notes": "",
            "processed_at": "2026-01-01T12:00:00+00:00",
        }
        md = render_from_db(row)
        assert "❌ Failed" in md
        assert "Alice Sample" in md
