"""`plan` command — predictive capacity planner."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()


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
    safety_target: float = typer.Option(
        None,
        "--safety-target",
        "-s",
        help="Min refusal rate 0.0-1.0 (TR134/TR142 screen). Opt-in; rejects unsafe cells.",
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
    if safety_target is not None and not 0.0 <= safety_target <= 1.0:
        console.print("[red]Error:[/] --safety-target must be between 0.0 and 1.0.")
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
        safety_target=safety_target,
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
            safety_target=safety_target,
        )
