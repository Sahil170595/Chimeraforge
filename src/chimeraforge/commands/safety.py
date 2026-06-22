"""`safety` command — measure a model's refusal rate against a live backend."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()


def safety(
    model: str = typer.Option(
        ...,
        "--model",
        "-m",
        help="Model name/tag (e.g. llama3.2-3b).",
    ),
    prompts_file: str = typer.Option(
        ...,
        "--prompts",
        "-p",
        help="Refusal-probe prompts file, one per line. Bring your own benchmark "
        "(e.g. HarmBench, AdvBench); none is bundled.",
    ),
    backend: str = typer.Option(
        "ollama",
        "--backend",
        "-B",
        help="Serving backend (ollama supported; vllm/tgi not yet).",
    ),
    quant: str = typer.Option(
        None,
        "--quant",
        "-q",
        help="Quantization label, for comparison against bundled TR134/TR142 data.",
    ),
    safety_target: float = typer.Option(
        None,
        "--safety-target",
        "-s",
        help="Min refusal rate 0.0-1.0; exit 1 if the measured rate falls below it.",
    ),
    base_url: str = typer.Option(
        None,
        "--base-url",
        help="Backend URL override.",
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
    """Screen a live model's refusal rate on a set of probe prompts.

    Where ``plan --safety-target`` decides from bundled TR134/TR142 data, this
    measures the actual model: it sends each prompt, classifies refusals with a
    rule-based judge, and reports the measured refusal rate -- so you can screen
    a (model, quant) the bundled table does not cover.
    """
    import asyncio
    import logging
    from pathlib import Path

    from rich.progress import Progress, SpinnerColumn, TextColumn

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    if safety_target is not None and not 0.0 <= safety_target <= 1.0:
        console.print("[red]Error:[/] --safety-target must be between 0.0 and 1.0.")
        raise typer.Exit(code=1)

    # Load prompts (user-provided; no attack corpus ships with the package)
    p = Path(prompts_file)
    if not p.is_file():
        console.print(f"[red]Error:[/] prompts file not found: {prompts_file}")
        raise typer.Exit(code=1)
    prompts = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not prompts:
        console.print(f"[red]Error:[/] prompts file '{prompts_file}' has no non-empty lines.")
        raise typer.Exit(code=1)

    from chimeraforge.safety import run_safety_screen

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            disable=not console.is_terminal,  # no live spinner when piped/redirected
        ) as progress:
            task = progress.add_task(f"Screening {model} ({len(prompts)} prompts)...", total=None)

            def _on_progress(done: int, total: int) -> None:
                progress.update(task, description=f"Screening {model} ({done}/{total})...")

            result = asyncio.run(
                run_safety_screen(
                    model=model,
                    prompts=prompts,
                    backend_name=backend,
                    quant=quant,
                    base_url=base_url,
                    on_progress=_on_progress,
                )
            )
    except NotImplementedError as exc:
        console.print(f"[red]Error:[/] {exc}")
        raise typer.Exit(code=1)
    except (RuntimeError, ValueError) as exc:
        # RuntimeError: health/model pre-flight or all-prompts-failed; ValueError: unknown backend
        console.print(f"[red]Error:[/] {exc}")
        raise typer.Exit(code=1)

    # Compare against bundled gate data: resolve the (possibly Ollama-tagged)
    # model + quant to a registry model by family/params, then look it up.
    from chimeraforge.planner.identity import parse_identity, resolve_model

    registry_model = resolve_model(model)
    ident = parse_identity(model, quant)
    resolved = f"{registry_model} {ident.quant}" if registry_model and ident.quant else None
    expected = None
    rtsi = "UNKNOWN"
    if registry_model and ident.quant:
        from chimeraforge.planner.models import load_bundled_models

        sm = load_bundled_models().safety
        expected = sm.predict_refusal(registry_model, ident.quant)
        rtsi = sm.rtsi_risk(registry_model, ident.quant)

    passed = safety_target is None or result.refusal_rate >= safety_target

    if output_json:
        import json as json_mod

        out = result.to_dict()
        out["expected_refusal"] = expected
        out["rtsi_risk"] = rtsi
        out["resolved_to"] = resolved
        out["safety_target"] = safety_target
        out["passed"] = passed
        # highlight=False + soft_wrap: emit plain JSON so `--json | jq` is clean
        # and not broken by Rich's syntax highlighting when colour is forced.
        console.print(json_mod.dumps(out, indent=2), highlight=False, soft_wrap=True)
    else:
        _print_panel(result, expected, rtsi, resolved, safety_target, passed)

    if not passed:
        raise typer.Exit(code=1)


def _print_panel(result, expected, rtsi, resolved, safety_target, passed) -> None:
    """Render the screen result as a Rich panel."""
    from rich.panel import Panel
    from rich.table import Table

    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column("Key", style="dim")
    t.add_column("Value")
    t.add_row("Model", result.model)
    t.add_row("Quant", result.quant or "(unspecified)")
    t.add_row("Backend", result.backend)
    n_label = f"{result.n_prompts}"
    if result.n_errors:
        n_label += f" ({result.n_errors} errored)"
    t.add_row("Prompts screened", n_label)
    t.add_row("Refusal rate", f"[bold]{result.refusal_rate:.3f}[/] (measured)")
    if expected is not None:
        drift = result.refusal_rate - expected
        drift_color = "green" if drift >= -0.05 else "red"
        t.add_row("Expected (bundled)", f"{expected:.3f}  [dim]({resolved})[/]")
        t.add_row("Drift", f"[{drift_color}]{drift:+.3f}[/]")
    elif resolved is not None:
        t.add_row("Expected (bundled)", f"n/a ([dim]{resolved}[/] not in safety data)")
    else:
        t.add_row("Expected (bundled)", "n/a (no matching bundled model)")
    risk_color = {"HIGH": "bold red", "MODERATE": "yellow", "LOW": "green"}.get(rtsi, "dim")
    t.add_row("RTSI risk", f"[{risk_color}]{rtsi}[/]")
    if safety_target is not None:
        verdict = "[green]PASS[/]" if passed else "[bold red]FAIL[/]"
        t.add_row("Target", f"{safety_target:.2f} -> {verdict}")

    console.print()
    console.print(Panel(t, title="Safety Screen", border_style="green" if passed else "red"))
    if result.warnings:
        warns = "\n".join(f"  - {w}" for w in result.warnings[:10])
        if len(result.warnings) > 10:
            warns += f"\n  - ... and {len(result.warnings) - 10} more"
        console.print(Panel(warns, title="Warnings", border_style="yellow"))
