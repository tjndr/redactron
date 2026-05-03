"""Regression tests for BLD-FIX-2 — must FAIL before fixes are applied.

Tests:
1. Numeric token "103 9.22" does not crash the pipeline (assert → warn)
2. Numeric span skipped with warning log, not redacted
3. Safety-pass supplemental message is INFO, not WARNING
4. redactron run always writes .report.md + .report.json
5. --no-report skips report files
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from unittest.mock import patch

import fitz
import pytest

from redactron.detect.address_detector import detect_addresses
from redactron.extract.text_layer import TextLayer
from redactron.pipeline import run_pipeline
from redactron.profile import DetectionConfig, Profile, Subject


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pdf_with_text(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), text, fontsize=12)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _profile_with_address(address: str = "100 Main Street, Springfield, IL 62701") -> Profile:
    return Profile(
        subject=Subject(
            display_name="Alice Sample",
            addresses=[address],
        ),
        detection=DetectionConfig(fuzzy_match=True, match_threshold=0.85),
    )


def _minimal_profile() -> Profile:
    return Profile(
        subject=Subject(display_name="Alice Sample"),
        detection=DetectionConfig(fuzzy_match=True),
    )


# ---------------------------------------------------------------------------
# Test 1: numeric token "103 9.22" does NOT crash
# ---------------------------------------------------------------------------

class TestNumericTokenNoCrash:
    def test_pipeline_completes_with_numeric_table_cell(self, tmp_path: Path) -> None:
        """'103 9.22' in a table cell must not crash the pipeline (assert → warn)."""
        pdf_bytes = _make_pdf_with_text(
            "Statement\n103 9.22\nTotal: 103 9.22\nBalance: 0.00"
        )
        pdf_path = tmp_path / "numeric.pdf"
        pdf_path.write_bytes(pdf_bytes)
        out_path = tmp_path / "numeric_redacted.pdf"

        profile = _profile_with_address()
        # Must not raise AssertionError
        result = run_pipeline(pdf_path, out_path, profile, verify=False)
        assert out_path.exists()
        assert result is not None

    def test_detect_addresses_no_crash_on_numeric_span(self) -> None:
        """detect_addresses must not crash when a group normalises to a numeric token."""
        # Construct a TextLayer that looks like an address candidate but normalises
        # to a numeric-only string after usaddress processing
        layer = TextLayer(
            page_num=0,
            text="103 9.22",
            bbox=(0.0, 0.0, 100.0, 20.0),
            block_type=0,
        )
        profile = _profile_with_address()
        # Must not raise AssertionError
        result = detect_addresses([layer], profile)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Test 2: numeric span skipped with warning log
# ---------------------------------------------------------------------------

class TestNumericTokenWarningLog:
    def test_numeric_span_logs_warning_not_crash(self, caplog: pytest.LogCaptureFixture) -> None:
        """When a numeric span reaches the fuzzy-match gate, a WARNING is logged."""
        layer = TextLayer(
            page_num=0,
            text="103 9.22",
            bbox=(0.0, 0.0, 100.0, 20.0),
            block_type=0,
        )
        profile = _profile_with_address()
        with caplog.at_level(logging.WARNING, logger="redactron.detect.address_detector"):
            detect_addresses([layer], profile)
        # After fix: warning logged. Before fix: AssertionError raised (test fails).
        # We check that no AssertionError was raised (test reaching here = pass after fix).
        # The warning message check is a bonus assertion.
        warning_msgs = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
        # After fix this will contain the skip message; before fix the test crashes above
        assert any("numeric" in str(m).lower() or "skip" in str(m).lower()
                   for m in warning_msgs), (
            f"Expected a warning about numeric span, got: {warning_msgs}"
        )

    def test_numeric_span_not_redacted(self) -> None:
        """'103 9.22' must NOT be redacted (no profile match)."""
        layer = TextLayer(
            page_num=0,
            text="103 9.22",
            bbox=(0.0, 0.0, 100.0, 20.0),
            block_type=0,
        )
        profile = _profile_with_address()
        detections = detect_addresses([layer], profile)
        texts = [d.text for d in detections]
        assert "103 9.22" not in texts


# ---------------------------------------------------------------------------
# Test 3: safety-pass message is INFO, not WARNING
# ---------------------------------------------------------------------------

class TestSafetyPassLogLevel:
    def test_safety_pass_logs_info_not_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When pass 2 supplements pass 1, the log message must be INFO level."""
        # Build a PDF with a name that the detector will find
        pdf_bytes = _make_pdf_with_text("Alice Sample\nAlice Sample")
        pdf_path = tmp_path / "safety.pdf"
        pdf_path.write_bytes(pdf_bytes)
        out_path = tmp_path / "safety_redacted.pdf"

        profile = _minimal_profile()

        # Patch _detect_all to return detections on pass 1, then detections on pass 2
        # (simulating a safety-net trigger)
        from redactron.detect.presidio_detector import Detection
        fake_det = Detection(
            text="Alice Sample",
            entity_type="PERSON",
            score=1.0,
            page_num=0,
            bbox=(72.0, 90.0, 200.0, 110.0),
        )
        call_count = 0

        def mock_detect_all(doc, prof, threshold):  # type: ignore[no-untyped-def]
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [fake_det]  # pass 1: found something
            return [fake_det]  # pass 2: still found (triggers safety pass)

        with caplog.at_level(logging.DEBUG, logger="redactron.pipeline"):
            with patch("redactron.pipeline._detect_all", side_effect=mock_detect_all):
                try:
                    run_pipeline(pdf_path, out_path, profile, verify=False)
                except Exception:
                    pass  # pipeline may raise RedactionError after MAX_PASSES; that's ok

        # Check: no WARNING-level message about survivors in the successful path
        warning_msgs = [
            r.getMessage() for r in caplog.records
            if r.levelno == logging.WARNING
            and ("SURVIVORS" in r.getMessage() or "missed" in r.getMessage().lower()
                 or "bug report" in r.getMessage().lower())
        ]
        assert warning_msgs == [], (
            f"Safety-pass should not log WARNING about survivors; got: {warning_msgs}"
        )

        # Check: INFO message about supplemental pass exists (after fix)
        info_msgs = [
            r.getMessage() for r in caplog.records
            if r.levelno == logging.INFO and "supplemented" in r.getMessage().lower()
        ]
        assert info_msgs, (
            f"Expected INFO message about supplemental pass; got records: "
            f"{[r.getMessage() for r in caplog.records]}"
        )


# ---------------------------------------------------------------------------
# Test 4: run always writes .report.md + .report.json
# ---------------------------------------------------------------------------

class TestRunAlwaysWritesReports:
    def test_reports_written_by_default(self, tmp_path: Path) -> None:
        """run_pipeline must produce .report.md and .report.json alongside the PDF."""
        pdf_bytes = _make_pdf_with_text("Hello world. No PII here.")
        pdf_path = tmp_path / "doc.pdf"
        pdf_path.write_bytes(pdf_bytes)
        out_path = tmp_path / "doc_redacted.pdf"

        profile = _minimal_profile()
        run_pipeline(pdf_path, out_path, profile, verify=False)

        md_path = tmp_path / "doc_redacted.report.md"
        json_path = tmp_path / "doc_redacted.report.json"

        assert out_path.exists(), "Redacted PDF must exist"
        assert md_path.exists(), f"Report .md must exist at {md_path}"
        assert json_path.exists(), f"Report .json must exist at {json_path}"
        assert md_path.stat().st_size > 0, "Report .md must be non-empty"

    def test_reports_written_even_with_no_detections(self, tmp_path: Path) -> None:
        """Reports must be written even when 0 PII items are detected."""
        pdf_bytes = _make_pdf_with_text("Invoice #12345. Amount: $99.00.")
        pdf_path = tmp_path / "invoice.pdf"
        pdf_path.write_bytes(pdf_bytes)
        out_path = tmp_path / "invoice_redacted.pdf"

        profile = _minimal_profile()
        run_pipeline(pdf_path, out_path, profile, verify=False)

        assert (tmp_path / "invoice_redacted.report.md").exists()
        assert (tmp_path / "invoice_redacted.report.json").exists()


# ---------------------------------------------------------------------------
# Test 5: --no-report skips report files
# ---------------------------------------------------------------------------

class TestNoReportFlag:
    def test_no_report_skips_report_files(self, tmp_path: Path) -> None:
        """When write_reports=False, only the redacted PDF is written."""
        pdf_bytes = _make_pdf_with_text("Hello world.")
        pdf_path = tmp_path / "doc.pdf"
        pdf_path.write_bytes(pdf_bytes)
        out_path = tmp_path / "doc_redacted.pdf"

        profile = _minimal_profile()
        run_pipeline(pdf_path, out_path, profile, verify=False, write_reports=False)

        assert out_path.exists(), "Redacted PDF must exist"
        assert not (tmp_path / "doc_redacted.report.md").exists(), (
            "Report .md must NOT exist when write_reports=False"
        )
        assert not (tmp_path / "doc_redacted.report.json").exists(), (
            "Report .json must NOT exist when write_reports=False"
        )
