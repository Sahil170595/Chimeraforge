"""`bench` command - live LLM inference benchmarking."""

from __future__ import annotations

from pathlib import Path

import typer

from chimeraforge.planner.constants import QUANT_LEVELS
from rich.console import Console

console = Console()


def bench(
    ctx: typer.Context,
    model: str = typer.Option(
        None,
        "--model",
        "-m",
        help="Model name (e.g., llama3.2-3b, gemma3:latest).",
    ),
    backend: str = typer.Option(
        "ollama",
        "--backend",
        "-B",
        help="Built-in or installed plugin backend (see --list-backends).",
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
        help=(
            f"Sweep all {len(QUANT_LEVELS)} quantization levels "
            f"({', '.join(QUANT_LEVELS)}). Note: no backend accepts a per-request "
            f"quantization, so each row is labelled but not applied -- see the "
            f"warning on every swept result."
        ),
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
    list_backends: bool = typer.Option(
        False,
        "--list-backends",
        help="List built-in and installed plugin metadata without loading plugin code.",
    ),
    plan_path: str = typer.Option(
        None, "--plan", help="Benchmark a saved plan's selected candidate."
    ),
    candidate_index: int = typer.Option(
        0, "--candidate-index", help="Saved candidate index (zero based)."
    ),
    prompt: str = typer.Option(
        None, "--prompt", help="Actual prompt sent to the serving endpoint."
    ),
    concurrency: int = typer.Option(
        None, "--concurrency", help="Applied batch/server concurrency."
    ),
    secure: bool = typer.Option(
        False, "--secure", help="Require verified HTTPS for this active operation."
    ),
    bearer_env: str | None = typer.Option(
        None, "--bearer-env", help="Read bearer once from this named environment variable."
    ),
    ca_bundle: Path | None = typer.Option(
        None, "--ca-bundle", help="Private PEM CA bundle replacing default roots."
    ),
    client_cert: Path | None = typer.Option(
        None, "--client-cert", help="Client certificate PEM; requires key."
    ),
    client_key: Path | None = typer.Option(
        None, "--client-key", help="Unencrypted client key PEM; requires certificate."
    ),
) -> None:
    """Run LLM inference benchmarks against a live backend."""
    import asyncio
    import json as json_mod
    import logging
    from pathlib import Path

    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table

    from chimeraforge.commands._deps import require_extra

    require_extra("bench", "httpx")  # backends import httpx at module load

    from chimeraforge.monitor_connection import MonitorConnection, MonitorConnectionError
    from chimeraforge.plan_study import protect_output

    connection = None
    opted = secure or any(
        value is not None for value in (bearer_env, ca_bundle, client_cert, client_key)
    )
    if opted:
        try:
            if list_backends or not base_url:
                raise MonitorConnectionError("secure benchmark requires an explicit HTTPS endpoint")
            connection = MonitorConnection.from_env(
                base_url,
                bearer_env=bearer_env,
                ca_bundle=ca_bundle,
                client_cert=client_cert,
                client_key=client_key,
            )
        except MonitorConnectionError as exc:
            if output_json:
                import json

                typer.echo(json.dumps({"error": str(exc)}))
            else:
                console.print(str(exc), markup=False)
            raise typer.Exit(1) from None

    if plan_path:
        from chimeraforge.commands.bench_plan import run_saved

        run_saved(
            ctx,
            plan_path,
            candidate_index=candidate_index,
            model=model,
            backend=backend,
            prompt=prompt,
            runs=runs,
            workload=workload,
            rate=rate,
            concurrency=concurrency,
            base_url=base_url,
            output_dir=output_dir,
            output_json=output_json,
            quant=quant,
            all_quants=all_quants,
            context=context,
            list_backends=list_backends,
            **({"connection": connection} if connection is not None else {}),
        )
        return
    if candidate_index or prompt is not None or concurrency is not None:
        console.print(
            "[red]Error:[/] --candidate-index, --prompt and --concurrency require --plan."
        )
        raise typer.Exit(2)

    if list_backends:
        from chimeraforge.bench.backends import list_backends as backend_listing

        try:
            backends = backend_listing()
        except ValueError as exc:
            console.print(f"[red]Error:[/] {exc}")
            raise typer.Exit(code=1)
        if output_json:
            import json

            console.print(json.dumps(backends, indent=2), highlight=False, soft_wrap=True)
        else:
            table = Table("Name", "Kind", "Distribution", "Entry point")
            for row in backends:
                table.add_row(
                    row["name"], row["kind"], row["distribution"] or "", row["value"] or ""
                )
            console.print(table)
        return
    if not model:
        console.print("[red]Error:[/] --model is required unless --list-backends is used.")
        raise typer.Exit(code=1)

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

    if connection is not None:
        try:
            protect_output(out_path, connection._input_paths())
        except (ValueError, OSError) as exc:
            logging.getLogger(__name__).info(
                "Secure benchmark directory refused (%s)", type(exc).__name__
            )
            typer.echo(
                json_mod.dumps({"error": "secure benchmark output unavailable"})
                if output_json
                else "secure benchmark output unavailable"
            )
            raise typer.Exit(1) from None

    async def _run() -> None:
        import json as json_mod

        results = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            disable=output_json or not console.is_terminal,
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
                        **({"connection": connection} if connection is not None else {}),
                    )
                elif ctx_lengths:
                    progress.add_task("Running context sweep...", total=None)
                    results = await _run_context_sweep(
                        model=model,
                        backend_name=backend,
                        context_lengths=ctx_lengths,
                        quant=quant,
                        runs=runs,
                        workload=workload,
                        rate=rate,
                        base_url=base_url,
                        **({"connection": connection} if connection is not None else {}),
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
                        **({"connection": connection} if connection is not None else {}),
                    )
                    results = [result]
            except (RuntimeError, ValueError) as exc:
                # RuntimeError: health/model pre-flight failure; ValueError: unknown backend
                progress.stop()
                message = "secure benchmark failed" if connection is not None else str(exc)
                if connection is not None and output_json:
                    typer.echo(json_mod.dumps({"error": message}))
                else:
                    console.print(Panel(message, title="ERROR", border_style="red"))
                raise typer.Exit(code=1)

        if connection is not None:
            try:
                saved_path = _save_results(results, out_path, connection=connection)
            except (ValueError, OSError) as exc:
                logging.getLogger(__name__).info(
                    "Secure benchmark save refused (%s)", type(exc).__name__
                )
                typer.echo(
                    json_mod.dumps({"error": "secure benchmark output unavailable"})
                    if output_json
                    else "secure benchmark output unavailable"
                )
                raise typer.Exit(1) from None
        if output_json:
            data = [result_to_dict(r) for r in results]
            # highlight=False + soft_wrap: emit valid JSON for `--json | jq`; Rich
            # otherwise reflows long string values (width 79 when piped) and corrupts them.
            console.print(json_mod.dumps(data, indent=2), highlight=False, soft_wrap=True)
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
        if connection is None:
            saved_path = _save_results(results, out_path)
        diagnostics = Console(stderr=True) if output_json else console
        diagnostics.print(f"\n[green]Results saved to:[/] {saved_path}")

    asyncio.run(_run())
