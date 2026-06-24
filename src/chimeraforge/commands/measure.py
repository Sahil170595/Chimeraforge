"""`measure` command — benchmark a live model and fold it into the planner corpus."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()


def measure(
    model: str = typer.Option(
        ...,
        "--model",
        "-M",
        help="Model to benchmark (Ollama tag / served model name).",
    ),
    backend: str = typer.Option("ollama", "--backend", "-B", help="Serving backend."),
    quant: str = typer.Option(
        None, "--quant", "-q", help="Quant label for the lookup key (default: native)."
    ),
    runs: int = typer.Option(5, "--runs", help="N=1 sample count."),
    concurrency: int = typer.Option(
        4, "--concurrency", help="N at which to measure scaling (0/1 to skip)."
    ),
    context_length: int = typer.Option(2048, "--context-length", help="Context window in tokens."),
    base_url: str = typer.Option(None, "--base-url", help="Backend URL override."),
    ollama_url: str = typer.Option(None, "--ollama-url", help="Ollama base URL (for resolution)."),
    hf_token: str = typer.Option(None, "--hf-token", help="HF token (else $HF_TOKEN)."),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
) -> None:
    """Benchmark a live model and fold real throughput + scaling into the corpus.

    Runs the model through the actual ``bench`` machinery (N=1 throughput, service
    time, and concurrency scaling at N agents), then merges the measurements into
    a local fitted_models.json via the ``refit`` loop. ``plan`` and ``suggest``
    read that corpus automatically, so the model is planned on REAL numbers
    (provenance: measured) instead of a roofline estimate. Requires a live
    backend serving the model (e.g. pulled in Ollama).
    """
    import asyncio
    import json as json_mod
    import logging
    from dataclasses import asdict

    from rich.progress import Progress, SpinnerColumn, TextColumn

    from chimeraforge.measure import measure_model

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    if runs <= 0:
        console.print("[red]Error:[/] --runs must be positive.")
        raise typer.Exit(code=1)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            disable=not console.is_terminal,
        ) as progress:
            task = progress.add_task(f"Benchmarking {model}...", total=None)

            def _on_progress(done: int, total: int) -> None:
                progress.update(task, description=f"Benchmarking {model} ({done}/{total})...")

            result = asyncio.run(
                measure_model(
                    model,
                    backend=backend,
                    quant=quant,
                    runs=runs,
                    concurrency=concurrency,
                    context_length=context_length,
                    base_url=base_url,
                    ollama_url=ollama_url,
                    hf_token=hf_token,
                    on_progress=_on_progress,
                )
            )
    except RuntimeError as exc:
        console.print(f"[red]Error:[/] {exc}")
        console.print(
            "[dim]The model must be served by the backend "
            "(e.g. `ollama pull <model>`) before it can be measured.[/]"
        )
        raise typer.Exit(code=1)

    if output_json:
        console.print(json_mod.dumps(asdict(result), indent=2), highlight=False, soft_wrap=True)
    else:
        _print_panel(result)


def _print_panel(result) -> None:
    from rich.panel import Panel
    from rich.table import Table

    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column("Key", style="dim")
    t.add_column("Value")
    t.add_row("Model", f"{result.model} ({result.quant})")
    t.add_row("Backend", result.backend)
    cv_note = f"  [dim](CV {result.cv_n1:.1%})[/]" if result.cv_n1 else ""
    t.add_row(
        "N=1 throughput", f"[bold green]{result.tps_n1}[/] tok/s{cv_note}  [green](measured)[/]"
    )
    t.add_row("Service time", f"{result.service_ms} ms")
    if result.eta_at_n is not None:
        t.add_row(
            f"Scaling eta(N={result.n_concurrent})",
            f"{result.eta_at_n}  [green](measured)[/]  -> serial s={result.serial_fraction}",
        )
    else:
        t.add_row("Scaling", "[yellow]not measured[/] (skipped or concurrent run failed)")
    t.add_row("Corpus", result.corpus_path)

    console.print()
    console.print(Panel(t, title="Measured -> planner corpus", border_style="green"))
    console.print(
        "[dim]plan/suggest now use these measured numbers automatically "
        "(provenance: measured). Quality is still estimated -- measuring it needs "
        "the eval harness against the benchmark.[/]"
    )
    if result.warnings:
        warns = "\n".join(f"  - {w}" for w in result.warnings[:8])
        console.print(Panel(warns, title="Warnings", border_style="yellow"))
