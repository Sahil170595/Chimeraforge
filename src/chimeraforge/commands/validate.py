"""`validate` command - audit the planner's predictions against measurements.

Runs a pre-registered config matrix through the planner, joins each cell to a
measurement (live via `bench`, or from a captured file), and reports a
per-provenance-class error scorecard.
"""

from __future__ import annotations

import json as json_mod

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
        "Accepts a {cell_key: {metric: value}} map or a previous audit's JSON.",
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
        CellOutcome,
        Matrix,
        ValidationError,
        build_audit,
        classify,
        format_markdown,
        load_measurements,
        relative_error,
    )

    def _fail(msg: str) -> None:
        if output_json:
            console.print(json_mod.dumps({"error": msg}), highlight=False, soft_wrap=True)
        else:
            console.print(f"[red]Error:[/] {msg}")
        raise typer.Exit(code=1)

    if not measurements_path and not ollama_url:
        _fail(
            "nothing to compare against: pass --measurements FILE to score a captured "
            "run, or --ollama-url to benchmark live."
        )

    try:
        matrix = Matrix.load(matrix_path)
    except ValidationError as exc:
        _fail(str(exc))

    captured: dict[str, dict[str, float]] = {}
    if measurements_path:
        try:
            captured = load_measurements(measurements_path)
        except ValidationError as exc:
            _fail(str(exc))

    measure_live = bool(ollama_url) and not measurements_path
    if measure_live:
        from chimeraforge.commands._deps import require_extra

        require_extra("bench", "httpx")

    outcomes: list[CellOutcome] = []
    for cell in matrix.cells:
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
        cls = classify(picked.provenance, picked.tensor_parallel, picked.pipeline_parallel)

        measured = dict(captured.get(cell.key, {}))
        if measure_live:
            measured = _measure_cell(cell, ollama_url, runs, err_console)

        if not measured:
            outcomes.append(
                CellOutcome(
                    key=cell.key,
                    cell=cell,
                    provenance_class=cls,
                    predicted=predicted,
                    skipped="no measurement for this cell",
                )
            )
            continue

        errors = {}
        for metric, pred in predicted.items():
            err = relative_error(pred, measured.get(metric))
            if err is not None:
                errors[metric] = err
        outcomes.append(
            CellOutcome(
                key=cell.key,
                cell=cell,
                provenance_class=cls,
                predicted=predicted,
                measured=measured,
                errors=errors,
            )
        )

    audit = build_audit(matrix, outcomes)

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


def _measure_cell(cell, ollama_url: str, runs: int, err) -> dict[str, float]:
    """Benchmark one cell live. A failure is recorded per cell, never silently zeroed.

    Maps `bench`'s aggregate onto the planner's units deliberately: the planner
    predicts a mean single-stream rate and a tail latency, so throughput/TTFT come
    from the mean and p95 latency from the p95 of total duration -- not whichever
    percentile happens to flatter the prediction.
    """
    import asyncio

    from chimeraforge.bench.runner import run_benchmark

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
        return {}

    agg = res.aggregate
    out: dict[str, float] = {}
    if agg.throughput_tps.mean > 0:
        out["throughput_tps"] = float(agg.throughput_tps.mean)
    if agg.ttft_ms.mean > 0:
        out["ttft_ms"] = float(agg.ttft_ms.mean)
    if agg.total_duration_ms.p95 > 0:
        out["p95_latency_ms"] = float(agg.total_duration_ms.p95)
    if res.warnings:
        err.print(f"[dim]{cell.key}: {'; '.join(res.warnings[:2])}[/]")
    return out


def _print_table(audit) -> None:
    from chimeraforge.validate import CLASS_LOOKUP, CLASS_ORDER, LEAD_CLASS, MIN_CELLS_FOR_RATE

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
    for cls in CLASS_ORDER:
        rows = [r for r in audit.rows if r.provenance_class == cls]
        if not rows:
            continue
        title = cls
        if cls == LEAD_CLASS:
            title += "  (out-of-sample: the planner is predicting)"
        elif cls == CLASS_LOOKUP:
            title += "  (in-corpus: the data IS the prediction, not a test)"
        table = Table(title=title)
        table.add_column("Metric")
        table.add_column("n", justify="right")
        table.add_column("MAPE", justify="right")
        table.add_column("Median signed", justify="right")
        table.add_column("p90 abs", justify="right")
        table.add_column("Worst", justify="right")
        for r in rows:
            table.add_row(
                r.metric,
                f"{r.n}{'*' if r.underpowered else ''}",
                f"{r.mape:.1%}",
                f"{r.median_signed:+.1%}",
                f"{r.p90_abs:.1%}",
                f"{r.worst_error:+.1%}",
            )
        console.print(table)
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
