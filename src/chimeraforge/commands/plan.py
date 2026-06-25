"""`plan` command - predictive capacity planner."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()


def plan(
    model_size: str = typer.Option(
        "3b",
        "--model-size",
        "-m",
        help="Target model size class (e.g., 1b, 3b, 8b). Ignored if --model is given.",
    ),
    model: list[str] = typer.Option(
        None,
        "--model",
        "-M",
        help="Explicit model id(s): registry name, Ollama tag (ollama:NAME), or HF "
        "repo (org/name). Repeatable. Resolves real params/arch; overrides --model-size.",
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
    ollama_url: str = typer.Option(
        None,
        "--ollama-url",
        help="Ollama base URL; enables resolving --model tags via /api/show.",
    ),
    hf_token: str = typer.Option(
        None,
        "--hf-token",
        help="Hugging Face token for gated repos (else $HF_TOKEN).",
    ),
    no_network: bool = typer.Option(
        False,
        "--no-network",
        help="Never fetch metadata; resolve from registry/cache/overrides only.",
    ),
    params_b: float = typer.Option(
        None,
        "--params-b",
        help="Manual override: parameter count in billions (with a single --model).",
    ),
    n_layers: int = typer.Option(
        None,
        "--n-layers",
        help="Manual override: transformer block count.",
    ),
    n_kv_heads: int = typer.Option(
        None,
        "--n-kv-heads",
        help="Manual override: key/value head count.",
    ),
    d_head: int = typer.Option(
        None,
        "--d-head",
        help="Manual override: per-head dimension.",
    ),
    measure_first: bool = typer.Option(
        False,
        "--measure",
        help="Benchmark the --model live first (real throughput+scaling), then plan "
        "on the measured numbers. Requires a live backend serving the model.",
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

    Searches model x quantization x backend x instance-count space,
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
    from chimeraforge.planner.models import load_effective_models, load_models

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
    if latency_slo <= 0:
        console.print("[red]Error:[/] --latency-slo must be positive.")
        raise typer.Exit(code=1)
    if not 0.0 <= quality_target <= 1.0:
        console.print("[red]Error:[/] --quality-target must be between 0.0 and 1.0.")
        raise typer.Exit(code=1)
    if safety_target is not None and not 0.0 <= safety_target <= 1.0:
        console.print("[red]Error:[/] --safety-target must be between 0.0 and 1.0.")
        raise typer.Exit(code=1)
    if measure_first and not model:
        console.print("[red]Error:[/] --measure requires --model.")
        raise typer.Exit(code=1)

    # Optionally benchmark the model(s) live first, folding real throughput +
    # scaling into the local corpus so the plan below runs on measured numbers.
    if measure_first and model:
        import asyncio

        from chimeraforge.measure import measure_model

        for ident in model:
            console.print(f"[dim]Measuring {ident} on ollama (live)...[/]")
            try:
                mres = asyncio.run(measure_model(ident, backend="ollama", ollama_url=ollama_url))
            except RuntimeError as exc:
                console.print(f"[red]Error measuring '{ident}':[/] {exc}")
                raise typer.Exit(code=1)
            console.print(
                f"[green]Measured[/] {ident}: {mres.tps_n1} tok/s"
                + (f", eta(N={mres.n_concurrent})={mres.eta_at_n}" if mres.eta_at_n else "")
            )

    # Load models (explicit path > measured corpus > bundled)
    if models_path:
        try:
            planner_models = load_models(models_path)
        except FileNotFoundError:
            console.print(f"[red]Error:[/] models file not found: {models_path}")
            raise typer.Exit(code=1)
        except ValueError as exc:  # JSONDecodeError subclasses ValueError
            console.print(f"[red]Error:[/] invalid models file '{models_path}': {exc}")
            raise typer.Exit(code=1)
    else:
        planner_models = load_effective_models()

    # Resolve explicit --model ids to concrete specs (registry / Ollama / HF /
    # manual). When absent, fall back to the registry size-class search.
    specs: dict = {}
    if model:
        from chimeraforge.planner.resolver import ResolverError, resolve_spec

        overrides = {
            "params_b": params_b,
            "n_layers": n_layers,
            "n_kv_heads": n_kv_heads,
            "d_head": d_head,
        }
        if any(v is not None for v in overrides.values()) and len(model) != 1:
            console.print("[red]Error:[/] manual overrides require exactly one --model.")
            raise typer.Exit(code=1)
        for ident in model:
            try:
                spec = resolve_spec(
                    ident,
                    ollama_url=ollama_url,
                    hf_token=hf_token,
                    overrides=overrides,
                    allow_network=not no_network,
                )
            except ResolverError as exc:
                console.print(f"[red]Error resolving '{ident}':[/] {exc}")
                raise typer.Exit(code=1)
            specs[ident] = spec
            if not output_json:
                console.print(
                    f"[dim]Resolved[/] {ident} -> {spec.params_b}B "
                    f"({spec.n_layers}L/{spec.n_kv_heads}kv/{spec.d_head}d) "
                    f"[dim]source={spec.source}[/]"
                )
        target_models = list(specs.keys())
    else:
        target_models = find_models_for_size(model_size)

    gpu = get_gpu(hardware)
    if gpu is None:
        console.print(
            f"[yellow]Warning:[/] '{hardware}' not in hardware DB, "
            "using default RTX 4080 12GB specs."
        )

    # Trace rejections so a 0-result explains which gate was binding instead of
    # a generic "nothing fit". Only summarised when the search returns empty.
    trace: list = []

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
        specs=specs,
        trace=trace,
    )

    if output_json:
        # highlight=False + soft_wrap: emit plain JSON so it stays valid (Rich
        # would otherwise reflow long string values and corrupt them) and pipes
        # cleanly to `jq`.
        console.print(format_json(candidates), highlight=False, soft_wrap=True)
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
        if not candidates and trace:
            from chimeraforge.planner.engine import summarize_trace

            console.print("\n[bold]Why nothing fit:[/]")
            for line in summarize_trace(trace):
                console.print(f"  [yellow]-[/] {line}")
