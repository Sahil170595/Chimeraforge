"""Rich terminal output for the capacity planner."""

from __future__ import annotations

import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

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
    constraints.add_row("Budget", f"${budget}/mo")
    constraints.add_row("Hardware", hardware)

    # Recommendation table
    rec = Table(show_header=False, box=None, padding=(0, 2))
    rec.add_column("Key", style="bold cyan")
    rec.add_column("Value", style="bold")
    params_str = f"{MODEL_PARAMS_B.get(best.model, '?')}B"
    rec.add_row("Model", f"{best.model} ({params_str} params)")
    bpw_str = f"{QUANT_BPW.get(best.quant, '?')} bpw"
    rec.add_row("Quantization", f"{best.quant} ({bpw_str})")
    rec.add_row("Backend", best.backend)
    rec.add_row("Instances", str(best.n_agents))

    # Performance table
    perf = Table(show_header=False, box=None, padding=(0, 2))
    perf.add_column("Key", style="dim")
    perf.add_column("Value")
    perf.add_row("N=1 throughput", f"{best.throughput_tps} tok/s")
    perf.add_row("Total throughput", f"{best.total_throughput_tps} tok/s")
    perf.add_row("Scaling eta(N)", str(best.eta))
    perf.add_row("p95 latency", f"{best.p95_latency_ms} ms")
    perf.add_row("Utilisation", f"{best.utilisation:.1%}")

    # Quality + cost table
    cost_table = Table(show_header=False, box=None, padding=(0, 2))
    cost_table.add_column("Key", style="dim")
    cost_table.add_column("Value")
    tier_color = {
        "negligible": "green", "acceptable": "yellow",
        "concerning": "red", "unacceptable": "bold red",
    }.get(best.quality_tier, "white")
    cost_table.add_row("Quality score", str(best.quality))
    cost_table.add_row("Quality tier", f"[{tier_color}]{best.quality_tier}[/]")
    cost_table.add_row("VRAM per GPU", f"{best.vram_gb} GB")
    cost_table.add_row("Monthly cost", f"[bold green]${best.monthly_cost}[/]")
    cost_table.add_row("Cost per 1M tok", f"${best.cost_per_1m_tok}")

    # Assemble main panel
    output = Text()
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
        alt_table.add_column("p95 ms", justify="right")

        for i, alt in enumerate(alts, 1):
            alt_table.add_row(
                str(i), alt.model, alt.quant, alt.backend,
                str(alt.n_agents), f"${alt.monthly_cost}",
                str(alt.quality), f"{alt.p95_latency_ms}",
            )
        console.print(alt_table)

    console.print(f"\n  [dim]{len(candidates)} total viable configurations evaluated[/]\n")


def format_json(candidates: list[Candidate]) -> str:
    """Format candidates as JSON for programmatic consumption."""
    return json.dumps(
        [
            {
                "model": c.model,
                "quant": c.quant,
                "backend": c.backend,
                "n_agents": c.n_agents,
                "vram_gb": c.vram_gb,
                "quality": c.quality,
                "quality_tier": c.quality_tier,
                "throughput_tps": c.throughput_tps,
                "total_throughput_tps": c.total_throughput_tps,
                "eta": c.eta,
                "p95_latency_ms": c.p95_latency_ms,
                "utilisation": c.utilisation,
                "monthly_cost": c.monthly_cost,
                "cost_per_1m_tok": c.cost_per_1m_tok,
                "warnings": c.warnings,
            }
            for c in candidates
        ],
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
            name, f"{spec.vram_gb:.0f} GB",
            f"{spec.bandwidth_gbps:.0f}", f"${spec.cost_per_hour:.3f}",
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
