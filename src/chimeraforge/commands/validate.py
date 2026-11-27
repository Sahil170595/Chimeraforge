"""`validate` command - audit the planner's predictions against measurements.

Runs a pre-registered config matrix through the planner, joins each cell to a
measurement (live via `bench`, or from a captured file), and reports a
per-provenance-class error scorecard.
"""

from __future__ import annotations

import json as json_mod
import re
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

console = Console()
err_console = Console(stderr=True)


def validate(
    matrix_path: str = typer.Option(
        ...,
        "--matrix",
        help="Pre-registered config matrix (JSON). Fingerprinted into the audit, so "
        "a matrix edited after seeing results no longer matches its own report.",
    ),
    measurements_path: str = typer.Option(
        None,
        "--measurements",
        help="Captured measurements to score against, instead of benchmarking live. "
        "Accepts a schema-v2 sourced measurement file (every cell names its "
        "evidence class, source, capture date and metric definitions) or a previous "
        "audit's JSON.",
    ),
    ollama_url: str = typer.Option(
        None,
        "--ollama-url",
        help="Benchmark live against this Ollama instance (needs the `bench` extra).",
    ),
    runs: int = typer.Option(
        3,
        "--runs",
        help="Benchmark runs per cell when measuring live.",
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Write the full audit JSON here (every cell, including skips).",
    ),
    report: str = typer.Option(
        None,
        "--report",
        help="Write the markdown report here.",
    ),
    expect_fingerprint: str = typer.Option(
        None,
        "--expect-fingerprint",
        metavar="HASH",
        help="Require the full 64-character SHA-256 fingerprint. Without it the "
        "fingerprint is recomputed from whatever matrix was loaded and merely "
        "printed, so editing the matrix after seeing results yields a report that "
        "matches itself perfectly. Pass the hash recorded at pre-registration to "
        "make it a real gate.",
    ),
    min_scored_cells: int | None = typer.Option(
        None,
        "--min-scored-cells",
        min=1,
        help="Require this many distinct cells to contribute to the scorecard. "
        "Exit 4 below the minimum and still emit the audit.",
    ),
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Print the audit JSON to stdout instead of a table.",
    ),
    models_path: str = typer.Option(
        None,
        "--models-path",
        help="Path to fitted_models.json (default: bundled data).",
    ),
) -> None:
    """Audit planner predictions against measurements, by provenance class.

    Each prediction is already labeled measured / estimated / unknown. This checks
    how wrong each of those labels actually is, and publishes every cell.
    """
    from chimeraforge.bench.fleet_gate_output import _write
    from chimeraforge.validate import (
        Matrix,
        ValidationError,
        audit_cells,
        build_audit,
        format_markdown,
        load_measurements,
        models_file,
    )

    def _fail(msg: str) -> None:
        if output_json:
            typer.echo(json_mod.dumps({"error": msg}))
        else:
            console.print(f"[red]Error:[/] {msg}")
        raise typer.Exit(code=1)

    if ollama_url and measurements_path:
        # Before any file is read: a bad flag combination should not need a
        # well-formed matrix to be reported. Resolving it silently scored a stale
        # file while the operator believed a fresh benchmark had run, exit 0.
        _fail(
            "--ollama-url and --measurements are mutually exclusive: pass --ollama-url "
            "to benchmark live, or --measurements to score a captured file."
        )

    if not measurements_path and not ollama_url:
        _fail(
            "nothing to compare against: pass --measurements FILE to score a captured "
            "run, or --ollama-url to benchmark live."
        )

    try:
        matrix = Matrix.load(matrix_path)
    except ValidationError as exc:
        _fail(str(exc))

    if expect_fingerprint is not None:
        want = expect_fingerprint.strip().lower()
        if re.fullmatch(r"[0-9a-f]{64}", want) is None:
            _fail("expected matrix fingerprint must be a full SHA-256 hex digest")
        actual = matrix.fingerprint()
        if actual != want:
            _fail(
                f"matrix fingerprint {actual[:16]} does not match the expected "
                f"{want}: this is not the matrix that was pre-registered."
            )

    captured = {}
    if measurements_path:
        try:
            captured = load_measurements(measurements_path)
        except ValidationError as exc:
            _fail(str(exc))
        if captured.hardware != matrix.hardware:
            _fail(
                f"measurements were taken on {captured.hardware!r} but the matrix is "
                f"registered for {matrix.hardware!r}; scoring one against the other "
                "would grade the planner on the wrong GPU."
            )

    measure_live = bool(ollama_url)
    if measure_live:
        from chimeraforge.commands._deps import require_extra

        require_extra("bench", "httpx")

    # A published audit has to be reproducible by anyone, so predictions come from
    # the bundled corpus unless a corpus is named -- never from whatever `measure`
    # left in this user's cache, which run_plan would otherwise prefer.
    def _live(cell):
        if cell.backend != "ollama":
            return None, (
                f"live measurement runs on Ollama only; a {cell.backend} cell needs "
                "a captured --measurements file"
            )
        return _measure_cell(cell, ollama_url, runs, err_console), "live measurement failed"

    json_path = Path(output) if output else None
    markdown_path = Path(report) if report else None
    destinations = [path for path in (json_path, markdown_path) if path is not None]
    with models_file(models_path) as effective_models_path:
        protected = [
            path for path in (matrix_path, measurements_path, effective_models_path) if path
        ]
        try:
            _admit_output_paths(destinations, protected)
        except (ValueError, OSError, RuntimeError):
            _fail("audit output destinations must be valid, distinct files outside the inputs")
        outcomes = audit_cells(
            matrix, captured, effective_models_path, measure=_live if measure_live else None
        )
        audit = build_audit(
            matrix, outcomes, models_basis=models_path if models_path else "bundled"
        )
        audit_json = None
        try:
            if json_path is not None or output_json:
                audit_json = json_mod.dumps(audit.to_dict(), indent=2, allow_nan=False)
            buffers = []
            if json_path is not None and audit_json is not None:
                buffers.append(audit_json.encode("utf-8"))
            if markdown_path is not None:
                buffers.append(format_markdown(audit).encode("utf-8"))
            admitted = _admit_output_paths(destinations, protected)
            for path, raw in zip(admitted, buffers, strict=True):
                _write(path, raw)
        except (ValueError, OSError, RuntimeError):
            _fail("could not render or publish the requested audit output")

    if json_path is not None:
        err_console.print(f"[dim]audit JSON -> {output}[/]")
    if markdown_path is not None:
        err_console.print(f"[dim]report -> {report}[/]")

    if output_json:
        typer.echo(audit_json)
    else:
        _print_table(audit)

    if min_scored_cells is not None:
        scored = audit.scored_cell_count
        if scored < min_scored_cells:
            typer.echo(
                f"Audit coverage is insufficient: scored {scored} cell(s), "
                f"requires at least {min_scored_cells}.",
                err=True,
            )
            raise typer.Exit(code=4)


def _admit_output_paths(destinations: list[Path], protected: list[str]) -> list[Path]:
    from chimeraforge.commands._trace_output import preflight_trace_output
    from chimeraforge.plan_study import protect_output

    resolved = [path.resolve() for path in destinations]
    for index, path in enumerate(resolved):
        protect_output(path, (*protected, *resolved[:index], *resolved[index + 1 :]))
        preflight_trace_output(path)
    return resolved


def _measure_cell(cell, ollama_url: str, runs: int, err):
    """Benchmark one cell live into a sourced own-rig record, or None on failure.

    Maps `bench`'s aggregate onto the planner's units deliberately: the planner
    predicts a mean single-stream rate and a tail latency, so throughput/TTFT come
    from the mean and p95 latency from the p95 of total duration -- not whichever
    percentile happens to flatter the prediction. Ollama's throughput is
    ``eval_count / eval_duration`` and its TTFT ``prompt_eval_duration``, both
    server-timed, so the definitions below are what was actually measured.
    """
    import asyncio
    import datetime as dt
    from dataclasses import asdict

    from chimeraforge.bench.runner import run_benchmark
    from chimeraforge.validate import (
        DEF_DECODE,
        DEF_E2E_P95,
        DEF_TTFT,
        EVIDENCE_OWN_RIG,
        MeasuredCell,
        MeasuredMetric,
    )

    try:
        res = asyncio.run(
            run_benchmark(
                model=cell.model,
                backend_name="ollama",
                quant=cell.quant,
                base_url=ollama_url,
                runs=runs,
                context_length=cell.context_length,
            )
        )
    except Exception as exc:  # noqa: BLE001 - reported per cell, audit continues
        err.print(f"[yellow]measure failed[/] {cell.key}: {type(exc).__name__}: {exc}")
        return None

    agg = res.aggregate
    metrics = []
    if agg.throughput_tps.mean > 0:
        metrics.append(MeasuredMetric(DEF_DECODE, float(agg.throughput_tps.mean)))
    if agg.ttft_ms.mean > 0:
        metrics.append(MeasuredMetric(DEF_TTFT, float(agg.ttft_ms.mean)))
    if agg.total_duration_ms.p95 > 0:
        metrics.append(MeasuredMetric(DEF_E2E_P95, float(agg.total_duration_ms.p95)))
    if res.warnings:
        err.print(f"[dim]{cell.key}: {'; '.join(res.warnings[:2])}[/]")
    if not metrics:
        return None
    return MeasuredCell(
        key=cell.key,
        evidence=EVIDENCE_OWN_RIG,
        captured_at=dt.date.today().isoformat(),
        underspecified=False,
        metrics=tuple(metrics),
        environment=asdict(res.environment),
        engine_version=getattr(res.environment, "backend_version", None),
    )


def _print_table(audit) -> None:
    from chimeraforge.validate import (
        CLASS_LOOKUP,
        CLASS_ORDER,
        EVIDENCE_ORDER,
        LEAD_CLASS,
        MIN_CELLS_FOR_RATE,
    )

    console.print()
    console.print(
        f"[bold]Prediction-vs-measured audit[/]  {audit.hardware}  "
        f"[dim]matrix {audit.fingerprint[:12]} registered {audit.registered_at}[/]"
    )
    if not audit.rows:
        console.print(
            "[yellow]No cell produced a comparable measurement.[/] "
            "Every cell is still recorded in the audit JSON with its reason."
        )
    evidences = [e for e in (*EVIDENCE_ORDER, None) if any(r.evidence == e for r in audit.rows)]
    for evidence in evidences:
        for cls in CLASS_ORDER:
            rows = [r for r in audit.rows if r.provenance_class == cls and r.evidence == evidence]
            if not rows:
                continue
            title = f"{evidence} / {cls}" if evidence else cls
            if cls == LEAD_CLASS:
                title += "  (out-of-sample: the planner is predicting)"
            elif cls == CLASS_LOOKUP:
                title += "  (in-corpus row: the data IS the prediction)"
            table = Table(title=title)
            table.add_column("Metric")
            table.add_column("n", justify="right")
            table.add_column("In-band", justify="right")
            table.add_column("Median abs", justify="right")
            table.add_column("GMFE", justify="right")
            table.add_column("Bias", justify="right")
            table.add_column("Worst", justify="right")
            for r in rows:
                table.add_row(
                    r.metric,
                    f"{r.n}{'*' if r.underpowered else ''}",
                    "n/a" if r.pass_rate is None else f"{r.pass_rate:.0%}",
                    f"{r.median_abs:.1%}",
                    "n/a" if r.gmfe is None else f"{r.gmfe:.2f}x",
                    f"{r.median_signed:+.1%}",
                    f"{r.worst_error:+.1%}",
                )
            console.print(table)
    if audit.underspecified:
        console.print(
            f"[yellow]{len(audit.underspecified)} underspecified cell(s)[/] published in "
            "the JSON and report, kept out of every row above."
        )
    if any(r.underpowered for r in audit.rows):
        console.print(
            f"  [dim]* fewer than {MIN_CELLS_FOR_RATE} cells -- an anecdote, not a rate.[/]"
        )
    if audit.skipped:
        console.print(f"\n[yellow]{len(audit.skipped)} cell(s) skipped:[/]")
        for o in audit.skipped[:8]:
            console.print(f"  [dim]-[/] {escape(o.key)}: {escape(o.skipped or '')}")
        if len(audit.skipped) > 8:
            console.print(f"  [dim]... and {len(audit.skipped) - 8} more (all in the JSON)[/]")
    console.print(
        "\n  [dim]Positive = planner optimistic. Every cell, including the worst, is in "
        "the audit JSON.[/]\n"
    )
