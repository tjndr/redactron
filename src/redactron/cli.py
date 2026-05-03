"""redactron CLI — orchestration only, no business logic."""

import json as json_mod
from pathlib import Path
from typing import Optional

import typer

from redactron import __version__
from redactron.config import default_profile_path
from redactron.errors import RedactronError

app = typer.Typer(
    name="redactron",
    help="Local-only CLI for batch PII redaction in PDFs.",
    add_completion=False,
)


def _error(msg: str, debug: bool = False, exc: Optional[BaseException] = None) -> None:
    """Print a user-friendly error and exit 1."""
    typer.echo(f"Error: {msg}", err=True)
    if debug and exc is not None:
        import traceback
        traceback.print_exc()
    raise typer.Exit(1)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """redactron — local-only PDF PII redaction."""
    if ctx.invoked_subcommand is None:
        typer.echo("Use --help to see available commands.")


@app.command("version")
def version_cmd() -> None:
    """Show version and exit."""
    typer.echo(f"redactron {__version__}")


@app.command()
def init() -> None:
    """Create a default profile.yaml in ~/.redactron/."""
    profile_path = default_profile_path()
    if profile_path.exists():
        typer.echo(f"Profile already exists: {profile_path}")
        raise typer.Exit()

    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(_DEFAULT_PROFILE)
    typer.echo(f"Created profile: {profile_path}")
    typer.echo("Edit it to add your name, addresses, and other PII to redact.")


@app.command()
def run(
    path: Path = typer.Argument(..., help="PDF file or directory to redact."),
    profile: str = typer.Option("", "--profile", "-p", help="Profile YAML path."),
    output: str = typer.Option("", "--output", "-o", help="Output path."),
    threshold: float = typer.Option(0.5, "--threshold", "-t", help="Detection score threshold."),
    ocr: bool = typer.Option(False, "--ocr", help="Enable OCR fallback for image pages."),
    no_verify: bool = typer.Option(False, "--no-verify", help="Skip post-redaction verification."),
    json_output: bool = typer.Option(False, "--json", help="Output results as JSON."),
    debug: bool = typer.Option(False, "--debug", help="Show full stack traces on error."),
) -> None:
    """Redact PII from a PDF file or directory of PDFs."""
    try:
        _run_pipeline(
            path=path,
            profile_path=Path(profile) if profile else default_profile_path(),
            output=Path(output) if output else None,
            threshold=threshold,
            ocr=ocr,
            verify=not no_verify,
            json_output=json_output,
        )
    except RedactronError as exc:
        _error(str(exc), debug=debug, exc=exc)
    except Exception as exc:
        _error(f"Unexpected error: {exc}", debug=debug, exc=exc)


def _run_pipeline(
    path: Path,
    profile_path: Path,
    output: Optional[Path],
    threshold: float,
    ocr: bool,
    verify: bool,
    json_output: bool,
) -> None:
    """Orchestrate extract → detect → redact → verify for one or more PDFs."""
    from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn

    from redactron.detect.presidio_detector import detect
    from redactron.extract.text_layer import extract_text_layers, open_pdf
    from redactron.redact.engine import redact, save_redacted

    pdfs = _collect_pdfs(path)
    if not pdfs:
        typer.echo("No PDF files found.", err=True)
        raise typer.Exit(1)

    batch = len(pdfs) > 1
    results = []

    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        transient=True,
        disable=not batch or json_output,
    )
    with progress:
        task = progress.add_task("Redacting…", total=len(pdfs))
        for pdf_path in pdfs:
            progress.update(task, description=f"[cyan]{pdf_path.name}[/cyan]")
            out_path = _output_path(pdf_path, output, batch)
            doc = open_pdf(pdf_path)
            layers = extract_text_layers(doc)
            detections = detect(layers, score_threshold=threshold)
            redacted_doc = redact(doc, detections)
            save_redacted(redacted_doc, out_path)

            result: dict[str, object] = {
                "input": str(pdf_path),
                "output": str(out_path),
                "detections": len(detections),
                "verification": None,
            }

            if verify:
                from redactron.verify.verifier import verify_redaction
                vr = verify_redaction(redacted_doc, detections)
                result["verification"] = {"passed": vr.passed, "survivors": len(vr.survivors)}
                if not vr.passed:
                    progress.print(
                        f"WARNING: {len(vr.survivors)} PII item(s) survived "
                        f"redaction in {pdf_path.name}",
                    )

            results.append(result)
            progress.advance(task)

    if json_output:
        typer.echo(json_mod.dumps(results, indent=2))
    else:
        for r in results:
            status = "✓" if r.get("verification") is None or (
                isinstance(r["verification"], dict) and r["verification"]["passed"]
            ) else "✗"
            typer.echo(f"{status} {r['input']} → {r['output']} ({r['detections']} detections)")


def _collect_pdfs(path: Path) -> list[Path]:
    """Return list of PDF paths from a file or directory."""
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.rglob("*.pdf"))
    return []


def _output_path(input_path: Path, output: Optional[Path], batch: bool) -> Path:
    """Compute the output path for a redacted PDF."""
    stem = input_path.stem + "_redacted"
    name = stem + ".pdf"
    if output is None:
        return input_path.parent / name
    if batch:
        return output / name
    return output


_DEFAULT_PROFILE = """\
version: 1
name: default
subject:
  display_name: "Your Name"
  aliases: []
  addresses: []
  phones: []
  emails: []
  ssns: []
  account_numbers: []
  custom_patterns: []
detection:
  use_presidio: true
  presidio_entities:
    - PERSON
    - LOCATION
    - PHONE_NUMBER
    - EMAIL_ADDRESS
    - US_SSN
    - CREDIT_CARD
    - DATE_TIME
  fuzzy_match: true
  match_threshold: 0.85
  full_token_min_length: 2
  ocr_fallback: false
"""


if __name__ == "__main__":
    app()
