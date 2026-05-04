"""Tests for batch resilience — BLD-FIX-14.

Verifies that a batch run continues processing remaining files when one file
fails, collects errors with category + mitigation, and returns correct exit codes.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import fitz
from typer.testing import CliRunner

from redactron.cli import app
from redactron.errors import ExtractionError, NoTextLayerError
from redactron.pipeline import _categorize_error

runner = CliRunner(mix_stderr=False)


def _make_pdf(tmp_path: Path, name: str = "doc.pdf", text: str = "Hello World") -> Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    buf = io.BytesIO(doc.tobytes())
    doc2 = fitz.open(stream=buf, filetype="pdf")
    p = tmp_path / name
    doc2.save(str(p))
    return p


# ---------------------------------------------------------------------------
# Unit tests for _categorize_error
# ---------------------------------------------------------------------------

def test_categorize_no_text_layer() -> None:
    exc = NoTextLayerError("no text")
    cat, mit = _categorize_error(exc)
    assert cat == "OCR_REQUIRED"
    assert "ocr" in mit.lower()


def test_categorize_encrypted() -> None:
    exc = ExtractionError("PDF is encrypted")
    cat, mit = _categorize_error(exc)
    assert cat == "ENCRYPTED"
    assert "decrypt" in mit.lower()


def test_categorize_unknown() -> None:
    exc = RuntimeError("something weird")
    cat, mit = _categorize_error(exc)
    assert cat == "UNKNOWN"
    assert "debug" in mit.lower()


# ---------------------------------------------------------------------------
# Integration: batch continues on per-file failure
# ---------------------------------------------------------------------------

def test_batch_continues_on_one_failure(tmp_path: Path) -> None:
    """Batch of 3 PDFs: middle one raises; other two succeed."""
    pdf_dir = tmp_path / "in"
    pdf_dir.mkdir()
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    _make_pdf(pdf_dir, "a.pdf")
    _make_pdf(pdf_dir, "b.pdf")
    _make_pdf(pdf_dir, "c.pdf")

    call_count = 0

    def fake_pipeline(input_path: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal call_count
        call_count += 1
        if input_path.name == "b.pdf":
            raise ExtractionError("corrupt file")
        from redactron.pipeline import PipelineResult
        return PipelineResult(
            input_path=input_path,
            output_path=args[0],
            detections=[],
            detections_total=0,
            safety_passes=0,
            verification_passed=True,
            survivors=0,
        )

    with patch("redactron.pipeline.run_pipeline", side_effect=fake_pipeline):
        result = runner.invoke(
            app,
            ["run", str(pdf_dir), "--output", str(out_dir), "--no-verify", "--no-report"],
            env={"NO_BANNER": "1"},
        )

    assert call_count == 3, "All 3 files should be attempted"
    assert result.exit_code == 1  # some errored, some succeeded
    assert "b.pdf" in result.stderr
    assert "CORRUPT" in result.stderr or "corrupt" in result.stderr.lower()


def test_batch_all_fail_exits_2(tmp_path: Path) -> None:
    """All files fail → exit code 2."""
    pdf_dir = tmp_path / "in"
    pdf_dir.mkdir()
    _make_pdf(pdf_dir, "a.pdf")
    _make_pdf(pdf_dir, "b.pdf")

    def always_fail(input_path: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise ExtractionError("corrupt")

    with patch("redactron.pipeline.run_pipeline", side_effect=always_fail):
        result = runner.invoke(
            app,
            ["run", str(pdf_dir), "--no-verify", "--no-report"],
            env={"NO_BANNER": "1"},
        )

    assert result.exit_code == 2


def test_batch_all_succeed_exits_0(tmp_path: Path) -> None:
    """All files succeed → exit code 0."""
    pdf_dir = tmp_path / "in"
    pdf_dir.mkdir()
    _make_pdf(pdf_dir, "a.pdf")
    _make_pdf(pdf_dir, "b.pdf")

    from redactron.pipeline import PipelineResult

    def always_ok(input_path: Path, output_path: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        return PipelineResult(
            input_path=input_path,
            output_path=output_path,
            detections=[],
            detections_total=0,
            safety_passes=0,
            verification_passed=True,
            survivors=0,
        )

    with patch("redactron.pipeline.run_pipeline", side_effect=always_ok):
        result = runner.invoke(
            app,
            ["run", str(pdf_dir), "--no-verify", "--no-report"],
            env={"NO_BANNER": "1"},
        )

    assert result.exit_code == 0


def test_error_summary_shows_mitigation(tmp_path: Path) -> None:
    """Error output includes category and mitigation hint."""
    pdf_dir = tmp_path / "in"
    pdf_dir.mkdir()
    _make_pdf(pdf_dir, "scan.pdf")

    def ocr_required(input_path: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise NoTextLayerError("no text layer")

    with patch("redactron.pipeline.run_pipeline", side_effect=ocr_required):
        result = runner.invoke(
            app,
            ["run", str(pdf_dir), "--no-verify", "--no-report"],
            env={"NO_BANNER": "1"},
        )

    assert "OCR_REQUIRED" in result.stderr
    assert "ocr" in result.stderr.lower()
