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
        False, "--version", "-V",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """ChimeraForge — LLM deployment optimizer."""


@app.command()
def plan(
    model_size: str = typer.Option(
        "3b", "--model-size", "-m",
        help="Target model size class (e.g., 1b, 3b, 8b).",
    ),
    request_rate: float = typer.Option(
        1.0, "--request-rate", "-r",
        help="Requests per second.",
    ),
    latency_slo: float = typer.Option(
        5000.0, "--latency-slo", "-l",
        help="Max p95 latency in milliseconds.",
    ),
    quality_target: float = typer.Option(
        0.5, "--quality-target", "-q",
        help="Min composite quality score (0.0-1.0).",
    ),
    budget: float = typer.Option(
        100.0, "--budget", "-b",
        help="Max monthly cost in USD.",
    ),
    hardware: str = typer.Option(
        "RTX 4080 12GB", "--hardware", "-hw",
        help="GPU name from hardware DB.",
    ),
    context_length: int = typer.Option(
        2048, "--context-length",
        help="Context window length in tokens.",
    ),
    avg_tokens: int = typer.Option(
        128, "--avg-tokens",
        help="Average output tokens per request.",
    ),
    models_path: str = typer.Option(
        None, "--models-path",
        help="Path to fitted_models.json (default: bundled data).",
    ),
    output_json: bool = typer.Option(
        False, "--json",
        help="Output as JSON instead of Rich tables.",
    ),
    list_hardware: bool = typer.Option(
        False, "--list-hardware",
        help="List available GPUs in hardware DB.",
    ),
    list_models: bool = typer.Option(
        False, "--list-models",
        help="List available model sizes.",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
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
            candidates, hardware,
            request_rate=request_rate,
            latency_slo=latency_slo,
            quality_target=quality_target,
            budget=budget,
        )


@app.command()
def bench(
    model: str = typer.Option(
        ..., "--model", "-m",
        help="Model name (e.g., llama3.2-3b, gemma3:latest).",
    ),
    backend: str = typer.Option(
        "ollama", "--backend", "-B",
        help="Serving backend: ollama, vllm, tgi.",
    ),
    quant: str = typer.Option(
        None, "--quant", "-q",
        help="Quantization level (e.g., Q4_K_M).",
    ),
    all_quants: bool = typer.Option(
        False, "--all-quants",
        help="Sweep all 7 quantization levels.",
    ),
    workload: str = typer.Option(
        "single", "--workload", "-w",
        help="Workload profile: single, batch, server.",
    ),
    rate: float = typer.Option(
        None, "--rate",
        help="Request rate for server workload (req/s).",
    ),
    runs: int = typer.Option(
        5, "--runs", "-n",
        help="Number of benchmark runs per config.",
    ),
    context: str = typer.Option(
        None, "--context",
        help="Context lengths to sweep (comma-separated, e.g., 512,1024,2048).",
    ),
    base_url: str = typer.Option(
        None, "--base-url",
        help="Backend URL override.",
    ),
    output_dir: str = typer.Option(
        None, "--output-dir", "-o",
        help="Results directory override.",
    ),
    output_json: bool = typer.Option(
        False, "--json",
        help="Output as JSON instead of Rich tables.",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
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
                    task = progress.add_task("Running quant sweep...", total=None)
                    results = await _run_quant_sweep(
                        model=model,
                        backend_name=backend,
                        runs=runs,
                        workload=workload,
                        rate=rate,
                        base_url=base_url,
                    )
                elif context:
                    ctx_lengths = [int(c.strip()) for c in context.split(",")]
                    task = progress.add_task("Running context sweep...", total=None)
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
                    task = progress.add_task(
                        f"Benchmarking {model} on {backend}...", total=None,
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
