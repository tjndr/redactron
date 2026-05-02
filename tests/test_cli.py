"""Tests for src/redactron/cli.py."""

import io
from pathlib import Path

import fitz
from typer.testing import CliRunner

from redactron.cli import app

runner = CliRunner()


def _make_pdf_file(tmp_path: Path, name: str = "test.pdf", text: str = "Hello World") -> Path:
    """Write a simple PDF to disk and return its path."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    buf = io.BytesIO(doc.tobytes())
    doc2 = fitz.open(stream=buf, filetype="pdf")
    pdf_path = tmp_path / name
    doc2.save(str(pdf_path))
    return pdf_path


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "redactron" in result.output


def test_help() -> None:
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0


def test_init_creates_profile(tmp_path: Path) -> None:
    profile = tmp_path / "profile.yaml"
    result = runner.invoke(app, ["init"], env={"REDACTRON_PROFILE": str(profile)})
    assert result.exit_code == 0
    assert profile.exists()
    assert "version: 1" in profile.read_text()


def test_init_skips_if_exists(tmp_path: Path) -> None:
    profile = tmp_path / "profile.yaml"
    profile.write_text("existing")
    result = runner.invoke(app, ["init"], env={"REDACTRON_PROFILE": str(profile)})
    assert result.exit_code == 0
    assert "already exists" in result.output
    assert profile.read_text() == "existing"  # not overwritten


def test_run_single_pdf(tmp_path: Path) -> None:
    pdf = _make_pdf_file(tmp_path)
    result = runner.invoke(app, ["run", str(pdf), "--no-verify"])
    assert result.exit_code == 0
    out = tmp_path / "test_redacted.pdf"
    assert out.exists()


def test_run_produces_output_file(tmp_path: Path) -> None:
    pdf = _make_pdf_file(tmp_path)
    out = tmp_path / "out.pdf"
    result = runner.invoke(app, ["run", str(pdf), "--output", str(out), "--no-verify"])
    assert result.exit_code == 0
    assert out.exists()


def test_run_json_output(tmp_path: Path) -> None:
    import json
    pdf = _make_pdf_file(tmp_path)
    result = runner.invoke(app, ["run", str(pdf), "--no-verify", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert data[0]["input"] == str(pdf)


def test_run_missing_file_exits_nonzero(tmp_path: Path) -> None:
    result = runner.invoke(app, ["run", str(tmp_path / "nonexistent.pdf"), "--no-verify"])
    assert result.exit_code != 0


def test_run_directory_of_pdfs(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    for i in range(3):
        _make_pdf_file(pdf_dir, f"doc{i}.pdf")
    result = runner.invoke(
        app, ["run", str(pdf_dir), "--output", str(out_dir), "--no-verify"]
    )
    assert result.exit_code == 0
    assert len(list(out_dir.glob("*.pdf"))) == 3


def test_run_with_verify(tmp_path: Path) -> None:
    pdf = _make_pdf_file(tmp_path)
    result = runner.invoke(app, ["run", str(pdf)])
    assert result.exit_code == 0
    assert "✓" in result.output
