"""Rich terminal output for the capacity planner."""

from __future__ import annotations

import json
from dataclasses import asdict

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from chimeraforge.planner.constants import MODEL_PARAMS_B, QUANT_BPW
from chimeraforge.planner.engine import Candidate
from chimeraforge.planner.hardware import GPU_DB

console = Console()


def format_recommendation(
    candidates: list[Candidate],
    hardware: str,
    request_rate: float,
    latency_slo: float,
    quality_target: float,
    budget: float,
    safety_target: float | None = None,
) -> None:
    """Print recommendation using Rich panels and tables."""
    if not candidates:
        console.print(
            Panel(
                "[bold red]No viable configuration found.[/]\n\n"
                "Try: relaxing quality target, increasing budget,\n"
                "raising latency SLO, or using a larger GPU.",
                title="ChimeraForge Capacity Planner",
                border_style="red",
            )
        )
        return

    best = candidates[0]

    # Constraints table
    constraints = Table(show_header=False, box=None, padding=(0, 2))
    constraints.add_column("Key", style="dim")
    constraints.add_column("Value")
    constraints.add_row("Request rate", f"{request_rate} req/s")
    constraints.add_row("Latency SLO", f"{latency_slo} ms (p95)")
    constraints.add_row("Quality target", f"{quality_target}")
    constraints.add_row(
        "Safety target",
        f"{safety_target} (min refusal)" if safety_target is not None else "off",
    )
    constraints.add_row("Budget", f"${budget}/mo")
    constraints.add_row("Hardware", hardware)

    # Recommendation table
    rec = Table(show_header=False, box=None, padding=(0, 2))
    rec.add_column("Key", style="bold cyan")
    rec.add_column("Value", style="bold")
    params_val = best.params_b or MODEL_PARAMS_B.get(best.model, "?")
    rec.add_row("Model", f"{best.model} ({params_val}B params)")
    bpw_str = f"{QUANT_BPW.get(best.quant, '?')} bpw"
    rec.add_row("Quantization", f"{best.quant} ({bpw_str})")
    rec.add_row("Backend", best.backend)
    rec.add_row("Instances", str(best.n_agents))
    if best.model_source != "registry":
        rec.add_row("Source", f"[yellow]{best.model_source}[/] (off-registry)")

    # Performance table
    perf = Table(show_header=False, box=None, padding=(0, 2))
    perf.add_column("Key", style="dim")
    perf.add_column("Value")
    tp_basis = best.provenance.get("throughput", "measured")
    tp_color = "green" if tp_basis == "measured" else "yellow"
    perf.add_row("N=1 throughput", f"{best.throughput_tps} tok/s  [{tp_color}]({tp_basis})[/]")
    perf.add_row("Total throughput", f"{best.total_throughput_tps} tok/s")
    perf.add_row("Scaling eta(N)", str(best.eta))
    perf.add_row("p95 latency", f"{best.p95_latency_ms} ms")
    perf.add_row("Utilisation", f"{best.utilisation:.1%}")

    # Quality + cost table
    cost_table = Table(show_header=False, box=None, padding=(0, 2))
    cost_table.add_column("Key", style="dim")
    cost_table.add_column("Value")
    tier_color = {
        "negligible": "green",
        "acceptable": "yellow",
        "concerning": "red",
        "unacceptable": "bold red",
    }.get(best.quality_tier, "white")
    risk_color = {
        "HIGH": "bold red",
        "MODERATE": "yellow",
        "LOW": "green",
        "UNKNOWN": "dim",
    }.get(best.rtsi_risk, "white")
    refusal_str = (
        f"{best.safety_refusal}" if best.safety_refusal is not None else "n/a (unscreened)"
    )
    q_basis = best.provenance.get("quality", "measured")
    q_color = {"measured": "green", "estimated": "yellow", "unknown": "red"}.get(q_basis, "white")
    cost_table.add_row("Quality score", f"{best.quality}  [{q_color}]({q_basis})[/]")
    cost_table.add_row("Quality tier", f"[{tier_color}]{best.quality_tier}[/]")
    cost_table.add_row("Refusal rate", refusal_str)
    cost_table.add_row("RTSI risk", f"[{risk_color}]{best.rtsi_risk}[/]")
    cost_table.add_row("VRAM per GPU", f"{best.vram_gb} GB")
    cost_table.add_row("Monthly cost", f"[bold green]${best.monthly_cost}[/]")
    cost_table.add_row("Cost per 1M tok", f"${best.cost_per_1m_tok}")

    # Assemble main panel
    console.print()
    console.print(Panel(constraints, title="Constraints", border_style="dim"))
    console.print(Panel(rec, title="Recommendation", border_style="green"))
    console.print(Panel(perf, title="Performance", border_style="cyan"))
    console.print(Panel(cost_table, title="Quality & Cost", border_style="yellow"))

    # Warnings
    if best.warnings:
        warning_text = "\n".join(f"  - {w}" for w in best.warnings)
        console.print(Panel(warning_text, title="Warnings", border_style="red"))

    # Alternatives
    alts = candidates[1:5]
    if alts:
        alt_table = Table(title="Alternatives (next 4 cheapest)")
        alt_table.add_column("#", style="dim", width=3)
        alt_table.add_column("Model")
        alt_table.add_column("Quant")
        alt_table.add_column("Backend")
        alt_table.add_column("N", justify="right")
        alt_table.add_column("$/mo", justify="right")
        alt_table.add_column("Quality", justify="right")
        alt_table.add_column("Safety", justify="right")
        alt_table.add_column("p95 ms", justify="right")

        for i, alt in enumerate(alts, 1):
            alt_table.add_row(
                str(i),
                alt.model,
                alt.quant,
                alt.backend,
                str(alt.n_agents),
                f"${alt.monthly_cost}",
                str(alt.quality),
                f"{alt.safety_refusal}" if alt.safety_refusal is not None else "?",
                f"{alt.p95_latency_ms}",
            )
        console.print(alt_table)

    console.print(f"\n  [dim]{len(candidates)} total viable configurations evaluated[/]\n")


def format_json(candidates: list[Candidate]) -> str:
    """Format candidates as JSON for programmatic consumption."""
    return json.dumps([asdict(c) for c in candidates], indent=2)


def format_suggestions(
    ranked: list[Candidate],
    hardware: str,
    considered: int,
    dropped: int,
    errors: list[tuple[str, str]] | None = None,
) -> None:
    """Render discovered-and-ranked model suggestions as a Rich table."""
    errors = errors or []
    if not ranked:
        console.print(
            Panel(
                f"[bold red]No discovered model fits the constraints on {hardware}.[/]\n\n"
                f"{considered} model(s) considered; none passed the gates.\n"
                "Try: a larger GPU, higher budget/latency SLO, or a lower quality target.",
                title="ChimeraForge Suggest",
                border_style="red",
            )
        )
        _print_resolve_errors(errors)
        return

    table = Table(title=f"Suggested models for {hardware} (best config per model)")
    table.add_column("#", style="dim", width=3)
    table.add_column("Model")
    table.add_column("Src", style="dim")
    table.add_column("Params", justify="right")
    table.add_column("Quant")
    table.add_column("Backend")
    table.add_column("N", justify="right")
    table.add_column("$/mo", justify="right")
    table.add_column("Quality", justify="right")
    table.add_column("p95 ms", justify="right")

    for i, c in enumerate(ranked, 1):
        q_basis = c.provenance.get("quality", "measured")
        q_mark = "" if q_basis == "measured" else "~"
        tp_basis = c.provenance.get("throughput", "measured")
        tp_mark = "" if tp_basis == "measured" else "~"
        table.add_row(
            str(i),
            c.model,
            c.model_source.replace("registry-approx", "approx").replace("registry", "reg"),
            f"{c.params_b}B",
            c.quant,
            c.backend,
            str(c.n_agents),
            f"${c.monthly_cost}",
            f"{q_mark}{c.quality}",
            f"{tp_mark}{c.p95_latency_ms}",
        )
    console.print()
    console.print(table)
    console.print(
        f"  [dim]{len(ranked)} of {considered} considered models fit; "
        f"{dropped} dropped (VRAM/budget/latency/quality). "
        f"~ = estimated, not measured.[/]"
    )
    _print_resolve_errors(errors)


def _print_resolve_errors(errors: list[tuple[str, str]]) -> None:
    if not errors:
        return
    lines = "\n".join(f"  - {ident}: {msg}" for ident, msg in errors[:8])
    if len(errors) > 8:
        lines += f"\n  - ... and {len(errors) - 8} more"
    console.print(Panel(lines, title=f"Unresolved ({len(errors)})", border_style="yellow"))


def format_suggestions_json(
    ranked: list[Candidate],
    considered: int,
    errors: list[tuple[str, str]] | None = None,
) -> str:
    """Format ranked suggestions as JSON."""
    return json.dumps(
        {
            "considered": considered,
            "fit": len(ranked),
            "suggestions": [asdict(c) for c in ranked],
            "unresolved": [{"id": i, "error": m} for i, m in (errors or [])],
        },
        indent=2,
    )


def print_hardware_table() -> None:
    """Print GPU database as a Rich table."""
    table = Table(title="Available GPUs")
    table.add_column("GPU", style="bold")
    table.add_column("VRAM", justify="right")
    table.add_column("BW GB/s", justify="right")
    table.add_column("$/hr", justify="right")

    for name, spec in sorted(GPU_DB.items()):
        table.add_row(
            name,
            f"{spec.vram_gb:.0f} GB",
            f"{spec.bandwidth_gbps:.0f}",
            f"${spec.cost_per_hour:.3f}",
        )
    console.print(table)


def print_models_table() -> None:
    """Print model registry as a Rich table."""
    table = Table(title="Available Models")
    table.add_column("Model", style="bold")
    table.add_column("Params (B)", justify="right")

    for name, params in sorted(MODEL_PARAMS_B.items(), key=lambda x: x[1]):
        table.add_row(name, f"{params:.2f}")
    console.print(table)
