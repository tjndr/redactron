"""redactron CLI — orchestration only, no business logic."""

from __future__ import annotations

import json as json_mod
import logging
from pathlib import Path
from typing import Optional

import typer

from redactron import __version__
from redactron.config import default_profile_path
from redactron.errors import ProfileValidationError, RedactronError
from redactron.profile import Profile

log = logging.getLogger(__name__)

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
    subject: str = typer.Option("", "--subject", "-s", help="Subject slug for audit tagging."),
    no_report: bool = typer.Option(False, "--no-report", help="Skip writing report files."),
    debug: bool = typer.Option(False, "--debug", help="Show full stack traces on error."),
) -> None:
    """Redact PII from a PDF file or directory of PDFs."""
    from redactron.profile import load_profile

    profile_path = Path(profile) if profile else default_profile_path()
    try:
        loaded_profile = load_profile(profile_path)
    except ProfileValidationError as exc:
        msg = str(exc)
        typer.echo(
            f"❌ Profile error: {msg}\n"
            "See docs/PROFILE.md for the full schema. Use --debug for details.",
            err=True,
        )
        if debug:
            import traceback
            traceback.print_exc()
        raise typer.Exit(1) from exc

    log.info(
        "Loaded profile: %s (subject: %s)",
        loaded_profile.name,
        loaded_profile.subject.display_name,
    )

    try:
        _run_pipeline(
            path=path,
            profile=loaded_profile,
            output=Path(output) if output else None,
            threshold=threshold,
            verify=not no_verify,
            json_output=json_output,
            subject_id=subject,
            write_reports=not no_report,
        )
    except RedactronError as exc:
        _error(str(exc), debug=debug, exc=exc)
    except Exception as exc:
        _error(f"Unexpected error: {exc}", debug=debug, exc=exc)


def _run_pipeline(
    path: Path,
    profile: Profile,
    output: Optional[Path],
    threshold: float,
    verify: bool,
    json_output: bool,
    subject_id: str = "",
    write_reports: bool = True,
) -> None:
    """Orchestrate extract → detect → redact → verify for one or more PDFs."""
    from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn

    from redactron.pipeline import run_pipeline

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
            result = run_pipeline(
                pdf_path,
                out_path,
                profile,
                score_threshold=threshold,
                verify=verify,
                write_reports=write_reports,
            )

            r: dict[str, object] = {
                "input": str(result.input_path),
                "output": str(result.output_path),
                "detections": len(result.detections),
                "subject": subject_id or None,
                "verification": None,
            }
            if result.verification_passed is not None:
                r["verification"] = {
                    "passed": result.verification_passed,
                    "survivors": result.survivors,
                }
                if not result.verification_passed:
                    progress.print(
                        f"WARNING: {result.survivors} PII item(s) survived "
                        f"redaction in {pdf_path.name}",
                    )

            results.append(r)
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
  use_presidio: false
  presidio_entities: []
  fuzzy_match: true
  match_threshold: 0.85
  full_token_min_length: 2
  ocr_fallback: false
"""

# ---------------------------------------------------------------------------
# subject subcommand group
# ---------------------------------------------------------------------------

subject_app = typer.Typer(name="subject", help="Manage redaction subjects.")
app.add_typer(subject_app)


@subject_app.command("add")
def subject_add(
    subject_id: str = typer.Argument(..., help="Subject slug (e.g. 'alice-smith')."),
    display_name: str = typer.Option("", "--name", "-n", help="Display name."),
) -> None:
    """Create or update a subject entry in the audit log."""
    from redactron.audit.log import add_subject

    name = display_name or subject_id
    add_subject(subject_id, name)
    typer.echo(f"Subject '{subject_id}' ({name}) saved.")


@subject_app.command("list")
def subject_list() -> None:
    """List all subjects in the audit log."""
    from redactron.audit.log import list_subjects

    subjects = list_subjects()
    if not subjects:
        typer.echo("No subjects found. Use `redactron subject add <id>` to create one.")
        return
    for s in subjects:
        typer.echo(f"{s['id']:20s}  {s['display_name']:30s}  docs={s['document_count']}")


@subject_app.command("show")
def subject_show(
    subject_id: str = typer.Argument(..., help="Subject slug."),
) -> None:
    """Show details for a specific subject."""
    from redactron.audit.log import get_subject

    s = get_subject(subject_id)
    if s is None:
        typer.echo(f"Subject '{subject_id}' not found.", err=True)
        raise typer.Exit(1)
    typer.echo(f"ID:             {s['id']}")
    typer.echo(f"Display name:   {s['display_name']}")
    typer.echo(f"Created:        {s['created_at']}")
    typer.echo(f"Last used:      {s['last_used_at']}")
    typer.echo(f"Document count: {s['document_count']}")


# ---------------------------------------------------------------------------
# dry-run command
# ---------------------------------------------------------------------------


@app.command("dry-run")
def dry_run(
    path: Path = typer.Argument(..., help="PDF file or directory to scan."),
    profile: str = typer.Option("", "--profile", "-p", help="Profile YAML path."),
    threshold: float = typer.Option(0.5, "--threshold", "-t", help="Detection score threshold."),
    json_output: bool = typer.Option(False, "--json", help="Output results as JSON."),
    debug: bool = typer.Option(False, "--debug", help="Show full stack traces on error."),
) -> None:
    """Show what would be redacted without writing any output files.

    Exits 0 if detections found, 1 if none.
    """
    from redactron.profile import load_profile

    profile_path = Path(profile) if profile else default_profile_path()
    try:
        loaded_profile = load_profile(profile_path)
    except ProfileValidationError as exc:
        _error(str(exc), debug=debug, exc=exc)
        return

    pdfs = _collect_pdfs(path)
    if not pdfs:
        typer.echo("No PDF files found.", err=True)
        raise typer.Exit(1)

    try:
        all_detections = _dry_run_pipeline(pdfs, loaded_profile, threshold)
    except RedactronError as exc:
        _error(str(exc), debug=debug, exc=exc)
        return

    if json_output:
        import json as _json
        typer.echo(_json.dumps(
            [
                {
                    "file": str(d["file"]),
                    "page": d["page"],
                    "entity_type": d["entity_type"],
                    "text": d["text"],
                    "score": d["score"],
                }
                for d in all_detections
            ],
            indent=2,
        ))
    else:
        if not all_detections:
            typer.echo("No PII detected.")
            raise typer.Exit(1)
        # Print table
        typer.echo(f"{'File':<30} {'Page':>4}  {'Type':<20} {'Score':>5}  Text")
        typer.echo("-" * 90)
        for d in all_detections:
            fname = Path(str(d["file"])).name[:28]
            text_preview = str(d["text"])[:40]
            score = d["score"]
            etype = d["entity_type"]
            typer.echo(f"{fname:<30} {d['page']:>4}  {etype:<20} {score:>5.2f}  {text_preview}")
        typer.echo(f"\n{len(all_detections)} detection(s) across {len(pdfs)} file(s).")

    if not all_detections:
        raise typer.Exit(1)


def _dry_run_pipeline(
    pdfs: list[Path],
    profile: Profile,
    score_threshold: float,
) -> list[dict]:  # type: ignore[type-arg]
    """Run extract+detect only; return list of detection dicts."""
    from redactron.detect.account_detector import detect_custom_patterns
    from redactron.detect.address_detector import detect_addresses
    from redactron.detect.name_detector import detect_names
    from redactron.extract.text_layer import extract_text_layers, open_pdf
    from redactron.redact.partial import detect_account_numbers

    results = []
    for pdf_path in pdfs:
        doc = open_pdf(pdf_path)
        layers = extract_text_layers(doc)

        detections = []
        detections.extend(detect_names(layers, profile))
        detections.extend(detect_addresses(layers, profile))
        detections.extend(detect_account_numbers(doc, profile))
        detections.extend(detect_custom_patterns(layers, profile))

        if profile.detection.use_presidio and profile.detection.presidio_entities:
            from redactron.detect.presidio_detector import detect as presidio_detect
            detections.extend(
                presidio_detect(
                    layers,
                    entities=list(profile.detection.presidio_entities),
                    score_threshold=score_threshold,
                )
            )

        for det in detections:
            results.append({
                "file": pdf_path,
                "page": det.page_num,
                "entity_type": det.entity_type,
                "text": det.text,
                "score": det.score,
            })

    return results


# ---------------------------------------------------------------------------
# verify command
# ---------------------------------------------------------------------------


@app.command()
def verify(
    path: Path = typer.Argument(..., help="Redacted PDF to verify."),
    profile: str = typer.Option("", "--profile", "-p", help="Profile YAML path."),
    threshold: float = typer.Option(0.5, "--threshold", "-t", help="Detection score threshold."),
    json_output: bool = typer.Option(False, "--json", help="Output result as JSON."),
    debug: bool = typer.Option(False, "--debug", help="Show full stack traces on error."),
) -> None:
    """Verify a redacted PDF for PII survivors.

    Exits 0 if clean, 1 if survivors found.
    """
    from redactron.extract.text_layer import open_pdf
    from redactron.profile import load_profile
    from redactron.verify.verifier import verify_redaction

    profile_path = Path(profile) if profile else default_profile_path()
    try:
        loaded_profile = load_profile(profile_path)
    except ProfileValidationError as exc:
        _error(str(exc), debug=debug, exc=exc)
        return

    try:
        doc = open_pdf(path)
        result = verify_redaction(doc, loaded_profile, score_threshold=threshold)
    except RedactronError as exc:
        _error(str(exc), debug=debug, exc=exc)
        return

    if json_output:
        import json as _json
        typer.echo(_json.dumps({
            "passed": result.passed,
            "survivors": [s.text for s in result.survivors],
            "duration_ms": result.duration_ms,
        }, indent=2))
    else:
        if result.passed:
            ms = result.duration_ms
            typer.echo(f"✅ {path.name}: clean — no PII survivors detected ({ms}ms)")
        else:
            typer.echo(
                f"❌ {path.name}: {len(result.survivors)} PII survivor(s) detected:",
                err=True,
            )
            for s in result.survivors:
                typer.echo(f"  page {s.page_num}: [{s.entity_type}] {s.text!r}", err=True)

    if not result.passed:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# log command
# ---------------------------------------------------------------------------


@app.command("log")
def log_cmd(
    subject: str = typer.Option("", "--subject", "-s", help="Filter by subject slug."),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of rows to show."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Show recent audit log entries."""
    from redactron.audit.log import get_runs

    rows = get_runs(subject_id=subject or None, limit=limit)

    if json_output:
        import json as _json
        typer.echo(_json.dumps(rows, indent=2, default=str))
        return

    if not rows:
        typer.echo("No audit log entries found.")
        return

    typer.echo(f"{'ID':>4}  {'File':<30} {'Subject':<15} {'Det':>4} {'V':>1}  Processed")
    typer.echo("-" * 80)
    for r in rows:
        fname = (r.get("original_filename") or "")[:28]
        subj = (r.get("subject_id") or "")[:13]
        det = r.get("items_detected", 0)
        vp = r.get("verification_passed")
        v_icon = "✅" if vp == 1 else ("❌" if vp == 0 else "-")
        ts = str(r.get("processed_at", ""))[:19]
        typer.echo(f"{r['id']:>4}  {fname:<30} {subj:<15} {det:>4} {v_icon}  {ts}")


# ---------------------------------------------------------------------------
# report command
# ---------------------------------------------------------------------------


@app.command()
def report(
    run_id: int = typer.Argument(..., help="Audit log run ID (from `redactron log`)."),
) -> None:
    """Re-render the Markdown report for a past run from the audit log."""
    from redactron.audit.log import get_runs
    from redactron.report.markdown import render_from_db

    rows = get_runs(limit=run_id + 100)
    # rows are newest-first; find by id
    match = next((r for r in rows if r["id"] == run_id), None)
    if match is None:
        typer.echo(f"Run ID {run_id} not found in audit log.", err=True)
        raise typer.Exit(1)
    typer.echo(render_from_db(match))


if __name__ == "__main__":
    app()
