"""`suggest` command — discover and rank deployable models for your hardware."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()


def suggest(
    request_rate: float = typer.Option(1.0, "--request-rate", "-r", help="Requests per second."),
    latency_slo: float = typer.Option(
        5000.0, "--latency-slo", "-l", help="Max p95 latency in milliseconds."
    ),
    quality_target: float = typer.Option(
        0.5, "--quality-target", "-q", help="Min composite quality score (0.0-1.0)."
    ),
    safety_target: float = typer.Option(
        None, "--safety-target", "-s", help="Min refusal rate 0.0-1.0 (TR134/TR142 screen)."
    ),
    budget: float = typer.Option(100.0, "--budget", "-b", help="Max monthly cost in USD."),
    hardware: str = typer.Option(
        "RTX 4080 12GB", "--hardware", "-hw", help="GPU name from hardware DB."
    ),
    context_length: int = typer.Option(2048, "--context-length", help="Context window in tokens."),
    avg_tokens: int = typer.Option(128, "--avg-tokens", help="Average output tokens per request."),
    source: str = typer.Option(
        "ollama",
        "--source",
        help="Discovery source(s), comma-separated: ollama, hf, catalog. "
        "'catalog' uses the offline curated set (run `chimeraforge catalog build` first).",
    ),
    hf_limit: int = typer.Option(
        8, "--hf-limit", help="Max top-downloaded HF models to consider (network heavy)."
    ),
    ollama_url: str = typer.Option(None, "--ollama-url", help="Ollama base URL."),
    hf_token: str = typer.Option(
        None, "--hf-token", help="HF token for gated repos (else $HF_TOKEN)."
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
) -> None:
    """Discover models from Ollama / Hugging Face and rank them for your constraints.

    Pulls candidate models from a live Ollama install and/or the HF Hub, resolves
    each to real parameters + architecture, runs them through the same gate search
    as ``plan``, and shows the best deployable config per model. Off-registry
    models carry estimated (roofline) throughput and unscreened safety -- flagged
    as such.
    """
    import logging

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    sources = [s.strip().lower() for s in source.split(",") if s.strip()]
    valid = {"ollama", "hf", "catalog"}
    bad = [s for s in sources if s not in valid]
    if bad:
        console.print(
            f"[red]Error:[/] unknown --source value(s): {', '.join(bad)} (use ollama,hf,catalog)"
        )
        raise typer.Exit(code=1)
    if request_rate <= 0 or budget <= 0 or latency_slo <= 0:
        console.print("[red]Error:[/] request-rate, budget, and latency-slo must be positive.")
        raise typer.Exit(code=1)
    if not 0.0 <= quality_target <= 1.0:
        console.print("[red]Error:[/] --quality-target must be between 0.0 and 1.0.")
        raise typer.Exit(code=1)

    from chimeraforge.planner.discovery import (
        discover_identifiers,
        load_catalog,
        resolve_many,
        suggest as run_suggest,
    )
    from chimeraforge.planner.formatter import format_suggestions, format_suggestions_json
    from chimeraforge.planner.models import load_bundled_models
    from chimeraforge.planner.resolver import DEFAULT_OLLAMA_URL, ResolverError

    # When ollama is a source, resolve its tags via real /api/show metadata.
    eff_ollama_url = ollama_url or (DEFAULT_OLLAMA_URL if "ollama" in sources else None)

    specs: dict = {}
    errors: list = []

    # Catalog source: load pre-resolved specs offline (no network).
    if "catalog" in sources:
        specs.update(load_catalog())
        if not specs and sources == ["catalog"]:
            console.print(
                "[yellow]Catalog is empty.[/] Run [bold]chimeraforge catalog build[/] first."
            )
            raise typer.Exit(code=1)

    # Live sources: discover identifiers then resolve them.
    live_sources = [s for s in sources if s in ("ollama", "hf")]
    if live_sources:
        try:
            with console.status(f"Discovering models from {', '.join(live_sources)}..."):
                identifiers = discover_identifiers(
                    live_sources, ollama_url=eff_ollama_url, hf_token=hf_token, hf_limit=hf_limit
                )
        except ResolverError as exc:
            console.print(f"[red]Error:[/] {exc}")
            raise typer.Exit(code=1)
        if identifiers:
            with console.status(f"Resolving {len(identifiers)} models..."):
                resolved, errs = resolve_many(
                    identifiers, ollama_url=eff_ollama_url, hf_token=hf_token
                )
            specs.update(resolved)
            errors.extend(errs)

    if not specs:
        console.print("[red]Error:[/] none of the discovered models could be resolved.")
        for ident, msg in errors[:10]:
            console.print(f"  [dim]- {ident}: {msg}[/]")
        raise typer.Exit(code=1)

    models = load_bundled_models()
    ranked = run_suggest(
        models,
        specs,
        hardware=hardware,
        request_rate=request_rate,
        latency_slo=latency_slo,
        quality_target=quality_target,
        budget=budget,
        avg_tokens=avg_tokens,
        context_length=context_length,
        safety_target=safety_target,
    )

    n_considered = len(specs)
    n_dropped = n_considered - len(ranked)
    if output_json:
        console.print(
            format_suggestions_json(ranked, considered=n_considered, errors=errors),
            highlight=False,
            soft_wrap=True,
        )
    else:
        format_suggestions(
            ranked,
            hardware=hardware,
            considered=n_considered,
            dropped=n_dropped,
            errors=errors,
        )
