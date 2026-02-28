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
