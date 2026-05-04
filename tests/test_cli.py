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


def test_version_flag() -> None:
    """--version and -V top-level flags print version and exit 0."""
    for flag in ["--version", "-V"]:
        result = runner.invoke(app, [flag])
        assert result.exit_code == 0, f"{flag} exited {result.exit_code}"
        assert "redactron" in result.output


def test_help() -> None:
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0


def test_init_creates_directory(tmp_path: Path) -> None:
    """init creates ~/.redactron/ dir and audit.db; no profile.yaml."""
    redactron_dir = tmp_path / ".redactron"
    result = runner.invoke(
        app, ["init"],
        env={"HOME": str(tmp_path), "REDACTRON_DB": str(redactron_dir / "audit.db")},
    )
    assert result.exit_code == 0
    assert redactron_dir.exists()
    assert not (redactron_dir / "profile.yaml").exists()


def test_init_warns_on_legacy_profile(tmp_path: Path) -> None:
    """init warns if legacy profile.yaml already exists."""
    redactron_dir = tmp_path / ".redactron"
    redactron_dir.mkdir()
    (redactron_dir / "profile.yaml").write_text("version: 1\n")
    result = runner.invoke(
        app, ["init"],
        env={"HOME": str(tmp_path), "REDACTRON_DB": str(redactron_dir / "audit.db")},
    )
    assert result.exit_code == 0
    assert "Legacy" in result.output or "deprecated" in result.output.lower()


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
    result = CliRunner(mix_stderr=False).invoke(app, ["run", str(pdf), "--no-verify", "--json"])
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
        app, ["run", str(pdf_dir), "--output", str(out_dir), "--no-verify"],
        env={"NO_BANNER": "1"},
    )
    assert result.exit_code == 0
    assert len(list((out_dir / "redacted").glob("*.pdf"))) == 3


def test_run_with_verify(tmp_path: Path) -> None:
    pdf = _make_pdf_file(tmp_path)
    result = runner.invoke(app, ["run", str(pdf)])
    assert result.exit_code == 0
    assert "✓" in result.output


def test_batch_progress_produces_all_outputs(tmp_path: Path) -> None:
    """Batch run on 5 PDFs produces 5 output files (progress bar enabled)."""
    pdf_dir = tmp_path / "in"
    pdf_dir.mkdir()
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    for i in range(5):
        _make_pdf_file(pdf_dir, f"file{i}.pdf")
    result = runner.invoke(
        app, ["run", str(pdf_dir), "--output", str(out_dir), "--no-verify"],
        env={"NO_BANNER": "1"},
    )
    assert result.exit_code == 0
    assert len(list((out_dir / "redacted").glob("*.pdf"))) == 5


def test_batch_json_output_has_all_entries(tmp_path: Path) -> None:
    """Batch --json output contains one entry per PDF."""
    import json
    pdf_dir = tmp_path / "in"
    pdf_dir.mkdir()
    for i in range(3):
        _make_pdf_file(pdf_dir, f"doc{i}.pdf")
    result = CliRunner(mix_stderr=False).invoke(
        app, ["run", str(pdf_dir), "--no-verify", "--json"]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 3


def test_collect_pdfs_single_file(tmp_path: Path) -> None:
    """_collect_pdfs returns single file as list."""
    from redactron.cli import _collect_pdfs
    pdf = _make_pdf_file(tmp_path)
    assert _collect_pdfs(pdf) == [pdf]


def test_collect_pdfs_directory(tmp_path: Path) -> None:
    """_collect_pdfs returns all PDFs in directory, sorted."""
    from redactron.cli import _collect_pdfs
    for name in ["b.pdf", "a.pdf", "c.pdf"]:
        _make_pdf_file(tmp_path, name)
    result = _collect_pdfs(tmp_path)
    assert [p.name for p in result] == ["a.pdf", "b.pdf", "c.pdf"]


def test_collect_pdfs_nonexistent_returns_empty(tmp_path: Path) -> None:
    """_collect_pdfs returns empty list for nonexistent path."""
    from redactron.cli import _collect_pdfs
    assert _collect_pdfs(tmp_path / "ghost") == []


def test_output_path_single_file(tmp_path: Path) -> None:
    """_output_path for single file uses stem_redacted.pdf."""
    from redactron.cli import _output_path
    p = tmp_path / "doc.pdf"
    result = _output_path(p, None, False)
    assert result == tmp_path / "doc_redacted.pdf"


def test_output_path_batch_uses_output_dir(tmp_path: Path) -> None:
    """_output_path in batch mode places file in output_dir/redacted/."""
    from redactron.cli import _output_path
    out_dir = tmp_path / "out"
    result = _output_path(tmp_path / "doc.pdf", out_dir, True)
    assert result == out_dir / "redacted" / "doc_redacted.pdf"
