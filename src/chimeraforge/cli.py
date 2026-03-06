"""ChimeraForge CLI — Typer application with subcommands."""

from __future__ import annotations

import typer
from rich.console import Console

import chimeraforge

console = Console()

app = typer.Typer(
    name="chimeraforge",
    help="LLM deployment optimizer — backed by 70,000+ real measurements.",
    no_args_is_help=True,
    add_completion=False,
)


def version_callback(value: bool) -> None:
    if value:
        console.print(f"chimeraforge {chimeraforge.__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """ChimeraForge — LLM deployment optimizer."""


@app.command()
def plan(
    model_size: str = typer.Option(
        "3b",
        "--model-size",
        "-m",
        help="Target model size class (e.g., 1b, 3b, 8b).",
    ),
    request_rate: float = typer.Option(
        1.0,
        "--request-rate",
        "-r",
        help="Requests per second.",
    ),
    latency_slo: float = typer.Option(
        5000.0,
        "--latency-slo",
        "-l",
        help="Max p95 latency in milliseconds.",
    ),
    quality_target: float = typer.Option(
        0.5,
        "--quality-target",
        "-q",
        help="Min composite quality score (0.0-1.0).",
    ),
    budget: float = typer.Option(
        100.0,
        "--budget",
        "-b",
        help="Max monthly cost in USD.",
    ),
    hardware: str = typer.Option(
        "RTX 4080 12GB",
        "--hardware",
        "-hw",
        help="GPU name from hardware DB.",
    ),
    context_length: int = typer.Option(
        2048,
        "--context-length",
        help="Context window length in tokens.",
    ),
    avg_tokens: int = typer.Option(
        128,
        "--avg-tokens",
        help="Average output tokens per request.",
    ),
    models_path: str = typer.Option(
        None,
        "--models-path",
        help="Path to fitted_models.json (default: bundled data).",
    ),
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON instead of Rich tables.",
    ),
    list_hardware: bool = typer.Option(
        False,
        "--list-hardware",
        help="List available GPUs in hardware DB.",
    ),
    list_models: bool = typer.Option(
        False,
        "--list-models",
        help="List available model sizes.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable debug logging.",
    ),
) -> None:
    """Recommend optimal LLM deployment configuration.

    Searches model × quantization × backend × instance-count space,
    filtering through VRAM, quality, latency, and budget gates.
    """
    import logging

    from chimeraforge.planner.engine import enumerate_candidates, find_models_for_size
    from chimeraforge.planner.formatter import (
        format_json,
        format_recommendation,
        print_hardware_table,
        print_models_table,
    )
    from chimeraforge.planner.hardware import get_gpu
    from chimeraforge.planner.models import load_bundled_models, load_models

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    if list_hardware:
        print_hardware_table()
        raise typer.Exit()

    if list_models:
        print_models_table()
        raise typer.Exit()

    # Validate inputs
    if request_rate <= 0:
        console.print("[red]Error:[/] --request-rate must be positive.")
        raise typer.Exit(code=1)
    if avg_tokens <= 0:
        console.print("[red]Error:[/] --avg-tokens must be positive.")
        raise typer.Exit(code=1)
    if context_length <= 0:
        console.print("[red]Error:[/] --context-length must be positive.")
        raise typer.Exit(code=1)
    if budget <= 0:
        console.print("[red]Error:[/] --budget must be positive.")
        raise typer.Exit(code=1)
    if not 0.0 <= quality_target <= 1.0:
        console.print("[red]Error:[/] --quality-target must be between 0.0 and 1.0.")
        raise typer.Exit(code=1)

    # Load models
    if models_path:
        planner_models = load_models(models_path)
    else:
        planner_models = load_bundled_models()

    target_models = find_models_for_size(model_size)

    gpu = get_gpu(hardware)
    if gpu is None:
        console.print(
            f"[yellow]Warning:[/] '{hardware}' not in hardware DB, "
            "using default RTX 4080 12GB specs."
        )

    candidates = enumerate_candidates(
        models=planner_models,
        target_models=target_models,
        hardware=hardware,
        request_rate=request_rate,
        latency_slo=latency_slo,
        quality_target=quality_target,
        budget=budget,
        avg_tokens=avg_tokens,
        context_length=context_length,
    )

    if output_json:
        console.print(format_json(candidates))
    else:
        format_recommendation(
            candidates,
            hardware,
            request_rate=request_rate,
            latency_slo=latency_slo,
            quality_target=quality_target,
            budget=budget,
        )


@app.command()
def bench(
    model: str = typer.Option(
        ...,
        "--model",
        "-m",
        help="Model name (e.g., llama3.2-3b, gemma3:latest).",
    ),
    backend: str = typer.Option(
        "ollama",
        "--backend",
        "-B",
        help="Serving backend: ollama, vllm, tgi.",
    ),
    quant: str = typer.Option(
        None,
        "--quant",
        "-q",
        help="Quantization level (e.g., Q4_K_M).",
    ),
    all_quants: bool = typer.Option(
        False,
        "--all-quants",
        help="Sweep all 7 quantization levels.",
    ),
    workload: str = typer.Option(
        "single",
        "--workload",
        "-w",
        help="Workload profile: single, batch, server.",
    ),
    rate: float = typer.Option(
        None,
        "--rate",
        help="Request rate for server workload (req/s).",
    ),
    runs: int = typer.Option(
        5,
        "--runs",
        "-n",
        help="Number of benchmark runs per config.",
    ),
    context: str = typer.Option(
        None,
        "--context",
        help="Context lengths to sweep (comma-separated, e.g., 512,1024,2048).",
    ),
    base_url: str = typer.Option(
        None,
        "--base-url",
        help="Backend URL override.",
    ),
    output_dir: str = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Results directory override.",
    ),
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON instead of Rich tables.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable debug logging.",
    ),
) -> None:
    """Run LLM inference benchmarks against a live backend."""
    import asyncio
    import logging
    from pathlib import Path

    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table

    from chimeraforge.bench.metrics import result_to_dict
    from chimeraforge.bench.runner import (
        run_benchmark as _run_benchmark,
        run_context_sweep as _run_context_sweep,
        run_quant_sweep as _run_quant_sweep,
        save_results as _save_results,
    )

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    # Validate inputs
    if runs <= 0:
        console.print("[red]Error:[/] --runs must be positive.")
        raise typer.Exit(code=1)
    if rate is not None and rate <= 0:
        console.print("[red]Error:[/] --rate must be positive.")
        raise typer.Exit(code=1)

    # Validate context lengths early
    ctx_lengths: list[int] | None = None
    if context:
        try:
            ctx_lengths = [int(c.strip()) for c in context.split(",")]
            if any(c <= 0 for c in ctx_lengths):
                raise ValueError("non-positive")
        except ValueError:
            console.print(
                "[red]Error:[/] --context must be comma-separated positive integers "
                "(e.g., 512,1024,2048)."
            )
            raise typer.Exit(code=1)

    # Determine output directory
    if output_dir:
        out_path = Path(output_dir)
    else:
        try:
            from platformdirs import user_data_dir

            out_path = Path(user_data_dir("chimeraforge")) / "results"
        except ImportError:
            out_path = Path.home() / ".chimeraforge" / "results"

    async def _run() -> None:
        import json as json_mod

        results = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            try:
                if all_quants:
                    progress.add_task("Running quant sweep...", total=None)
                    results = await _run_quant_sweep(
                        model=model,
                        backend_name=backend,
                        runs=runs,
                        workload=workload,
                        rate=rate,
                        base_url=base_url,
                    )
                elif ctx_lengths:
                    progress.add_task("Running context sweep...", total=None)
                    results = await _run_context_sweep(
                        model=model,
                        backend_name=backend,
                        context_lengths=ctx_lengths,
                        runs=runs,
                        workload=workload,
                        rate=rate,
                        base_url=base_url,
                    )
                else:
                    progress.add_task(
                        f"Benchmarking {model} on {backend}...",
                        total=None,
                    )
                    result = await _run_benchmark(
                        model=model,
                        backend_name=backend,
                        quant=quant,
                        workload=workload,
                        runs=runs,
                        rate=rate,
                        base_url=base_url,
                    )
                    results = [result]
            except RuntimeError as exc:
                progress.stop()
                console.print(Panel(str(exc), title="ERROR", border_style="red"))
                raise typer.Exit(code=1)

        if output_json:
            data = [result_to_dict(r) for r in results]
            console.print(json_mod.dumps(data, indent=2))
        else:
            for r in results:
                agg = r.aggregate
                q_label = r.quant or "default"
                title = f"{r.model} | {r.backend} | {q_label} | ctx={r.context_length}"

                table = Table(title=title, show_header=True, header_style="bold cyan")
                table.add_column("Metric", style="bold")
                table.add_column("Mean", justify="right")
                table.add_column("P50", justify="right")
                table.add_column("P95", justify="right")
                table.add_column("P99", justify="right")
                table.add_column("StdDev", justify="right")

                table.add_row(
                    "Throughput (tok/s)",
                    f"{agg.throughput_tps.mean:.1f}",
                    f"{agg.throughput_tps.p50:.1f}",
                    f"{agg.throughput_tps.p95:.1f}",
                    f"{agg.throughput_tps.p99:.1f}",
                    f"{agg.throughput_tps.stddev:.2f}",
                )
                table.add_row(
                    "TTFT (ms)",
                    f"{agg.ttft_ms.mean:.1f}",
                    f"{agg.ttft_ms.p50:.1f}",
                    f"{agg.ttft_ms.p95:.1f}",
                    f"{agg.ttft_ms.p99:.1f}",
                    f"{agg.ttft_ms.stddev:.2f}",
                )
                table.add_row(
                    "Total Duration (ms)",
                    f"{agg.total_duration_ms.mean:.1f}",
                    f"{agg.total_duration_ms.p50:.1f}",
                    f"{agg.total_duration_ms.p95:.1f}",
                    f"{agg.total_duration_ms.p99:.1f}",
                    f"{agg.total_duration_ms.stddev:.2f}",
                )

                console.print()
                console.print(table)

                info_parts = [
                    f"Runs: {agg.count}",
                    f"Total tokens: {agg.tokens_generated}",
                    f"Workload: {r.workload}",
                ]
                console.print(f"  [dim]{' | '.join(info_parts)}[/dim]")

                if r.warnings:
                    for w in r.warnings:
                        console.print(f"  [yellow]Warning:[/] {w}")

        # Save results
        saved_path = _save_results(results, out_path)
        console.print(f"\n[green]Results saved to:[/] {saved_path}")

    asyncio.run(_run())


@app.command()
def refit(
    bench_dir: str = typer.Option(
        None,
        "--bench-dir",
        "-d",
        help="Directory containing bench result JSON files.",
    ),
    bench_files: str = typer.Option(
        None,
        "--bench-files",
        "-f",
        help="Comma-separated paths to bench JSON files.",
    ),
    base_models: str = typer.Option(
        None,
        "--base-models",
        help="Path to base fitted_models.json (default: bundled).",
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path for updated fitted_models.json.",
    ),
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Output summary as JSON.",
    ),
    validate: bool = typer.Option(
        False,
        "--validate",
        help="Run validation checks on the refitted model.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable debug logging.",
    ),
) -> None:
    """Re-fit planner coefficients from benchmark results."""
    import json as json_mod
    import logging
    from pathlib import Path

    from rich.panel import Panel

    from chimeraforge.refit.fitter import refit_from_bench, save_fitted_models

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    # Collect bench paths
    paths: list[Path] = []
    if bench_dir:
        d = Path(bench_dir)
        if not d.is_dir():
            console.print(f"[red]Error:[/] --bench-dir '{bench_dir}' is not a directory.")
            raise typer.Exit(code=1)
        paths.extend(sorted(d.glob("*.json")))
    if bench_files:
        for f in bench_files.split(","):
            p = Path(f.strip())
            if not p.is_file():
                console.print(f"[red]Error:[/] bench file '{f.strip()}' not found.")
                raise typer.Exit(code=1)
            paths.append(p)

    if not paths:
        console.print("[red]Error:[/] provide --bench-dir or --bench-files.")
        raise typer.Exit(code=1)

    base_path = Path(base_models) if base_models else None
    merged, summary = refit_from_bench(paths, base_path)

    # Determine output path
    if output:
        out = Path(output)
    else:
        try:
            from platformdirs import user_data_dir

            out = Path(user_data_dir("chimeraforge")) / "fitted_models.json"
        except ImportError:
            out = Path.home() / ".chimeraforge" / "fitted_models.json"

    saved = save_fitted_models(merged, out)

    if output_json:
        console.print(json_mod.dumps(summary, indent=2))
    else:
        lines = [
            f"Bench results loaded: {summary['bench_results_loaded']}",
            f"Throughput entries updated: {summary['throughput_entries_updated']}",
            f"Quant multipliers updated: {summary['quant_multipliers_updated']}",
            f"Service times updated: {summary['service_times_updated']}",
            f"Power law re-fit: {summary['power_law_refit']}",
        ]
        if summary.get("warnings"):
            lines.append("")
            for w in summary["warnings"]:
                lines.append(f"[yellow]Warning:[/] {w}")
        console.print(Panel("\n".join(lines), title="Refit Summary", border_style="green"))
        console.print(f"[green]Saved to:[/] {saved}")

    if validate:
        from chimeraforge.refit.validator import (
            format_validation_json,
            format_validation_table,
            validate_fitted_models,
        )

        vresult = validate_fitted_models(merged)
        if output_json:
            console.print(format_validation_json(vresult))
        else:
            format_validation_table(vresult, console)
        if not vresult.passed:
            raise typer.Exit(code=1)


@app.command()
def compare(
    baseline: str = typer.Option(
        ...,
        "--baseline",
        "-b",
        help="Path to baseline bench result JSON.",
    ),
    candidate: str = typer.Option(
        ...,
        "--candidate",
        "-c",
        help="Path(s) to candidate bench result JSON (comma-separated).",
    ),
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable debug logging.",
    ),
) -> None:
    """Compare benchmark results between runs."""
    import logging
    from pathlib import Path

    from chimeraforge.compare.comparator import (
        compare_results,
        format_comparison_json,
        format_comparison_summary,
        format_comparison_table,
    )

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    baseline_path = Path(baseline)
    if not baseline_path.is_file():
        console.print(f"[red]Error:[/] baseline file '{baseline}' not found.")
        raise typer.Exit(code=1)

    candidate_paths: list[Path] = []
    for c in candidate.split(","):
        p = Path(c.strip())
        if not p.is_file():
            console.print(f"[red]Error:[/] candidate file '{c.strip()}' not found.")
            raise typer.Exit(code=1)
        candidate_paths.append(p)

    rows = compare_results(baseline_path, candidate_paths)

    if output_json:
        console.print(format_comparison_json(rows))
    else:
        format_comparison_table(rows, console)
        format_comparison_summary(rows, console)


@app.command(name="eval")
def eval_cmd(
    predictions: str = typer.Option(
        None,
        "--predictions",
        "-p",
        help="Path to predictions file (one per line).",
    ),
    references: str = typer.Option(
        None,
        "--references",
        "-r",
        help="Path to references file (one per line).",
    ),
    task: str = typer.Option(
        None,
        "--task",
        "-t",
        help="Built-in task name (general_knowledge, summarization, code).",
    ),
    model: str = typer.Option(
        "unknown",
        "--model",
        "-m",
        help="Model name identifier.",
    ),
    quant: str = typer.Option(
        None,
        "--quant",
        "-q",
        help="Quantization level (e.g., Q4_K_M).",
    ),
    list_tasks_flag: bool = typer.Option(
        False,
        "--list-tasks",
        help="List available built-in evaluation tasks.",
    ),
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable debug logging.",
    ),
) -> None:
    """Evaluate LLM output quality with text-similarity metrics."""
    import logging

    from chimeraforge.eval.runner import format_eval_json, format_eval_table, run_eval
    from chimeraforge.eval.tasks import get_task, list_tasks

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    if list_tasks_flag:
        for name in list_tasks():
            console.print(f"  {name}")
        raise typer.Exit()

    if task:
        try:
            t = get_task(task)
        except KeyError as exc:
            console.print(f"[red]Error:[/] {exc}")
            raise typer.Exit(code=1)
        refs = t.references
        task_name = t.name
        if predictions:
            from pathlib import Path as _Path

            pred_path = _Path(predictions)
            if not pred_path.is_file():
                console.print(f"[red]Error:[/] predictions file '{predictions}' not found.")
                raise typer.Exit(code=1)
            preds = pred_path.read_text(encoding="utf-8").strip().splitlines()
        else:
            if not output_json:
                console.print(
                    "[yellow]Note:[/] No --predictions file; "
                    "using task prompts as placeholder (scores will be low)."
                )
            preds = t.prompts
    elif predictions and references:
        from pathlib import Path

        pred_path = Path(predictions)
        ref_path = Path(references)
        if not pred_path.is_file():
            console.print(f"[red]Error:[/] predictions file '{predictions}' not found.")
            raise typer.Exit(code=1)
        if not ref_path.is_file():
            console.print(f"[red]Error:[/] references file '{references}' not found.")
            raise typer.Exit(code=1)
        preds = pred_path.read_text(encoding="utf-8").strip().splitlines()
        refs = ref_path.read_text(encoding="utf-8").strip().splitlines()
        task_name = f"file:{pred_path.name}"
    else:
        console.print("[red]Error:[/] provide --task or both --predictions and --references.")
        raise typer.Exit(code=1)

    result = run_eval(
        predictions=preds,
        references=refs,
        model=model,
        quant=quant,
        task=task_name,
    )

    if output_json:
        console.print(format_eval_json([result]))
    else:
        format_eval_table([result], console)


@app.command()
def report(
    results_dir: str = typer.Option(
        None,
        "--results-dir",
        "-d",
        help="Directory containing bench result JSON files.",
    ),
    results_files: str = typer.Option(
        None,
        "--results-files",
        "-f",
        help="Comma-separated paths to bench result JSON files.",
    ),
    fmt: str = typer.Option(
        "markdown",
        "--format",
        help="Output format: markdown or html.",
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path.",
    ),
    title: str = typer.Option(
        "ChimeraForge Benchmark Report",
        "--title",
        help="Report title.",
    ),
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Output report metadata as JSON.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable debug logging.",
    ),
) -> None:
    """Generate benchmark reports from result files."""
    import logging
    from pathlib import Path

    from chimeraforge.report.generator import (
        ReportConfig,
        format_report_rich,
        generate_report,
        load_results,
        save_report,
    )

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    # Collect result paths
    paths: list[Path] = []
    if results_dir:
        d = Path(results_dir)
        if not d.is_dir():
            console.print(f"[red]Error:[/] --results-dir '{results_dir}' is not a directory.")
            raise typer.Exit(code=1)
        paths.extend(sorted(d.glob("*.json")))
    if results_files:
        for f in results_files.split(","):
            p = Path(f.strip())
            if not p.is_file():
                console.print(f"[red]Error:[/] result file '{f.strip()}' not found.")
                raise typer.Exit(code=1)
            paths.append(p)

    if not paths:
        console.print("[red]Error:[/] provide --results-dir or --results-files.")
        raise typer.Exit(code=1)

    if fmt not in ("markdown", "html"):
        console.print("[red]Error:[/] --format must be 'markdown' or 'html'.")
        raise typer.Exit(code=1)

    config = ReportConfig(title=title, format=fmt)
    rpt = generate_report(paths, config)

    if output:
        out_path = Path(output)
        saved = save_report(rpt, out_path)
        console.print(f"[green]Report saved to:[/] {saved}")
    elif output_json:
        import json as json_mod

        meta = {
            "title": rpt.title,
            "format": rpt.format,
            "n_results": rpt.n_results,
            "timestamp": rpt.timestamp,
        }
        console.print(json_mod.dumps(meta, indent=2))
    else:
        format_report_rich(load_results(paths), console)
