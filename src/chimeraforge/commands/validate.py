"""`validate` command - audit the planner's predictions against measurements.

Runs a pre-registered config matrix through the planner, joins each cell to a
measurement (live via `bench`, or from a captured file), and reports a
per-provenance-class error scorecard.
"""

from __future__ import annotations

import json as json_mod
from contextlib import contextmanager

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
        help="Fail unless the matrix hashes to this value. Without it the "
        "fingerprint is recomputed from whatever matrix was loaded and merely "
        "printed, so editing the matrix after seeing results yields a report that "
        "matches itself perfectly. Pass the hash recorded at pre-registration to "
        "make it a real gate.",
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
    from chimeraforge.planner.service import run_plan
    from chimeraforge.validate import (
        Matrix,
        ValidationError,
        build_audit,
        format_markdown,
        load_measurements,
    )

    def _fail(msg: str) -> None:
        if output_json:
            console.print(json_mod.dumps({"error": msg}), highlight=False, soft_wrap=True)
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

    if expect_fingerprint:
        # The point of pre-registration: the hash is checked against what was
        # committed BEFORE any result was seen. Recomputing it from the loaded
        # matrix and printing it proves only that the file hashes to its own hash,
        # so editing a cell after seeing results produced a self-consistent report.
        actual = matrix.fingerprint()
        want = expect_fingerprint.strip().lower()
        if not actual.lower().startswith(want):
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
    with _models_file(models_path) as effective_models_path:
        outcomes = _audit_cells(
            matrix,
            captured,
            effective_models_path,
            ollama_url if measure_live else None,
            runs,
            run_plan,
        )

    audit = build_audit(matrix, outcomes, models_basis=models_path if models_path else "bundled")

    if output:
        from pathlib import Path

        Path(output).write_text(json_mod.dumps(audit.to_dict(), indent=2), encoding="utf-8")
        err_console.print(f"[dim]audit JSON -> {output}[/]")
    if report:
        from pathlib import Path

        Path(report).write_text(format_markdown(audit), encoding="utf-8")
        err_console.print(f"[dim]report -> {report}[/]")

    if output_json:
        console.print(json_mod.dumps(audit.to_dict(), indent=2), highlight=False, soft_wrap=True)
        return

    _print_table(audit)


@contextmanager
def _models_file(models_path: str | None):
    """Yield the corpus path predictions are made from: the given one, else bundled."""
    if models_path:
        yield models_path
        return
    import importlib.resources as pkg_resources

    bundled = pkg_resources.files("chimeraforge.planner") / "data" / "fitted_models.json"
    with pkg_resources.as_file(bundled) as p:
        yield str(p)


def _audit_cells(matrix, captured, models_path, ollama_url, runs, run_plan) -> list:
    from chimeraforge.validate import (
        CellOutcome,
        ValidationError,
        classify,
        outcome_from_measurement,
    )

    outcomes: list[CellOutcome] = []
    for cell in matrix.cells:
        if cell.batch != 1:
            # The audit predicts a single stream. Comparing a batch-B measurement
            # to it would grade the planner on a quantity it did not predict.
            outcomes.append(
                CellOutcome(
                    key=cell.key,
                    cell=cell,
                    provenance_class="unknown",
                    skipped=(
                        f"batch {cell.batch}: the audit compares against a single-stream "
                        "prediction, so a batched measurement is not comparable"
                    ),
                )
            )
            continue
        # Predict: pin the search to exactly this cell so the audit compares what it
        # registered, not whatever the planner would have preferred instead.
        try:
            result = run_plan(
                models=[cell.model],
                hardware=matrix.hardware,
                quality_target=0.0,
                budget=1e12,
                latency_slo=1e9,
                request_rate=1.0,
                avg_tokens=cell.avg_tokens,
                prompt_tokens=cell.prompt_tokens,
                context_length=cell.context_length,
                models_path=models_path,
                allow_network=False,
                overrides=cell.spec_dict or None,
            )
        except Exception as exc:  # noqa: BLE001 - one bad cell must not kill the audit
            outcomes.append(
                CellOutcome(
                    key=cell.key,
                    cell=cell,
                    provenance_class="unknown",
                    skipped=f"prediction failed: {type(exc).__name__}: {exc}",
                )
            )
            continue

        picked = next(
            (c for c in result.candidates if c.quant == cell.quant and c.backend == cell.backend),
            None,
        )
        if picked is None:
            outcomes.append(
                CellOutcome(
                    key=cell.key,
                    cell=cell,
                    provenance_class="unknown",
                    skipped=(
                        f"no candidate for {cell.quant} on {cell.backend} "
                        "(gated out; see `plan` for the binding gate)"
                    ),
                )
            )
            continue

        predicted = {
            "throughput_tps": picked.throughput_tps,
            "ttft_ms": picked.ttft_ms,
            "p95_latency_ms": picked.p95_latency_ms,
        }
        if picked.throughput_tps > 0:
            # The planner's service time for one request (LatencyModel): what a
            # single-request, no-queue end-to-end measurement is evidence about.
            predicted["e2e_latency_ms"] = (
                picked.ttft_ms + cell.avg_tokens / picked.throughput_tps * 1000.0
            )
        cls = classify(picked.provenance, picked.tensor_parallel, picked.pipeline_parallel)

        measurement = captured.get(cell.key)
        skip_reason = "no measurement for this cell"
        if ollama_url:
            if cell.backend == "ollama":
                measurement = _measure_cell(cell, ollama_url, runs, err_console)
            else:
                measurement = None
                skip_reason = (
                    f"live measurement runs on Ollama only; a {cell.backend} cell needs "
                    "a captured --measurements file"
                )

        if measurement is None:
            outcomes.append(
                CellOutcome(
                    key=cell.key,
                    cell=cell,
                    provenance_class=cls,
                    predicted=predicted,
                    skipped=skip_reason,
                )
            )
            continue

        try:
            outcomes.append(outcome_from_measurement(cell, cls, predicted, measurement))
        except ValidationError as exc:
            outcomes.append(
                CellOutcome(
                    key=cell.key,
                    cell=cell,
                    provenance_class=cls,
                    predicted=predicted,
                    skipped=str(exc),
                    measurement=measurement,
                    evidence=measurement.evidence,
                )
            )
    return outcomes


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
