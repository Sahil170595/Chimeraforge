"""Rich terminal output for the capacity planner."""

from __future__ import annotations

import json
from dataclasses import asdict

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from chimeraforge.planner.constants import MODEL_PARAMS_B, POWER_UTILISATION, QUANT_BPW
from chimeraforge.planner.engine import Candidate
from chimeraforge.planner.hardware import GPU_DB

# Marks that survive being skim-read, matching brief.PROVENANCE_MARK.
PROVENANCE_MARKS = {"measured": "", "derived": "", "extrapolated": "~", "estimated": "~"}


def _finite(obj):
    """Replace non-finite floats with None so the payload is real JSON.

    `cost_per_1m_tok_effective` is inf whenever throughput is zero, and CPython's
    json.dumps emits the bare token `Infinity` -- a CPython extension, not RFC
    8259. Python clients tolerate it; JSON.parse in a JS/TS MCP host throws and
    loses the whole tool result, not just the field.
    """
    import math

    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _finite(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_finite(v) for v in obj]
    return obj


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
    if best.tensor_parallel > 1 or best.pipeline_parallel > 1:
        par = (
            f"TP={best.tensor_parallel}"
            if best.tensor_parallel > 1
            else f"PP={best.pipeline_parallel}"
        )
        rec.add_row(
            "Instances",
            f"{best.n_agents} x {par}  ({best.gpus_total} GPUs total)",
        )
    else:
        rec.add_row("Instances", str(best.n_agents))
    if best.model_source != "registry":
        rec.add_row("Source", f"[yellow]{best.model_source}[/] (off-registry)")

    # Performance table
    perf = Table(show_header=False, box=None, padding=(0, 2))
    perf.add_column("Key", style="dim")
    perf.add_column("Value")
    # Absent label must fail to the WEAKEST claim, not the strongest: a Candidate
    # built without provenance rendered as "(measured)".
    tp_basis = best.provenance.get("throughput", "unknown")
    tp_color = "green" if tp_basis == "measured" else "yellow"
    perf.add_row("N=1 throughput", f"{best.throughput_tps} tok/s  [{tp_color}]({tp_basis})[/]")
    perf.add_row("Total throughput", f"{best.total_throughput_tps} tok/s")
    if best.effective_batch > 1:
        perf.add_row("Batch per GPU", f"{best.effective_batch} concurrent (continuous batching)")
    if best.ttft_ms:
        perf.add_row("TTFT (prefill)", f"{best.ttft_ms} ms")
    if best.tpot_ms:
        perf.add_row("TPOT (per token)", f"{best.tpot_ms} ms")
    perf.add_row("p95 latency", f"{best.p95_latency_ms} ms (end-to-end)")
    perf.add_row("Utilisation", f"{best.utilisation:.1%}")
    if best.max_concurrent_seqs:
        perf.add_row("Max concurrent/GPU", f"{best.max_concurrent_seqs} seqs (KV-cache bound)")

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
    q_basis = best.provenance.get("quality", "unknown")
    q_color = {"measured": "green", "estimated": "yellow", "unknown": "red"}.get(q_basis, "white")
    cost_table.add_row("Quality score", f"{best.quality}  [{q_color}]({q_basis})[/]")
    cost_table.add_row("Quality tier", f"[{tier_color}]{best.quality_tier}[/]")
    cost_table.add_row("Refusal rate", refusal_str)
    cost_table.add_row("RTSI risk", f"[{risk_color}]{best.rtsi_risk}[/]")
    cost_table.add_row("VRAM per GPU", f"{best.vram_gb} GB")
    cost_table.add_row("Monthly cost", f"[bold green]${best.monthly_cost}[/]")
    cost_table.add_row("Cost per 1M tok", f"${best.cost_per_1m_tok}")
    if best.tdp_watts > 0:
        load_pct = int(POWER_UTILISATION * 100)
        with_energy = best.cost_per_1m_tok + best.energy_cost_per_1m_tok
        cost_table.add_row(
            "Board power", f"{best.tdp_watts:.0f} W x{best.n_agents} (~{load_pct}% load)"
        )
        cost_table.add_row(
            "Energy / mo",
            f"${best.energy_cost_month}  [dim](self-hosted add-on; cloud $/hr bundles power)[/]",
        )
        cost_table.add_row("Cost/1M tok +energy", f"${with_energy:.4f}")
        cost_table.add_row("Perf per watt", f"{best.perf_per_watt} tok/s/W")

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
        alt_table.add_column("!", justify="right")

        for i, alt in enumerate(alts, 1):
            # Same ~ / ? marking as format_pareto and format_suggestions. Without
            # it an unknown quality of 0.5 (the neutral prior) was indistinguishable
            # from a measured 0.628, and only the WINNER's warnings were shown, so
            # an alternative carrying "RTSI refusal-instability risk: MODERATE"
            # displayed nothing at all.
            prov = alt.provenance or {}
            q_mark = PROVENANCE_MARKS.get(prov.get("quality", "unknown"), "?")
            t_mark = PROVENANCE_MARKS.get(prov.get("throughput", "unknown"), "?")
            alt_table.add_row(
                str(i),
                alt.model,
                alt.quant,
                alt.backend,
                str(alt.n_agents),
                f"${alt.monthly_cost}",
                f"{q_mark}{alt.quality}",
                f"{alt.safety_refusal}" if alt.safety_refusal is not None else "?",
                f"{t_mark}{alt.p95_latency_ms}",
                f"[yellow]{len(alt.warnings)}[/]" if alt.warnings else "",
            )
        console.print(alt_table)
        if any(a.warnings for a in alts):
            console.print(
                "  [dim]! = warning count on that alternative; `~` estimated, "
                "`?` unknown. Re-run with --model to see its warnings in full.[/]"
            )

    console.print(f"\n  [dim]{len(candidates)} total viable configurations evaluated[/]\n")


def format_json(candidates: list[Candidate]) -> str:
    """Format candidates as JSON for programmatic consumption."""
    return json.dumps(_finite([asdict(c) for c in candidates]), indent=2)


def format_launch(launch) -> None:
    """Print the serve command for the recommended config, plus its caveats."""
    body = launch.command
    if launch.env:
        exports = "\n".join(f"export {e}" for e in launch.env)
        body = f"{exports}\n\n{body}"
    console.print(
        Panel(
            body,
            title=f"Launch command ({launch.backend})",
            border_style="magenta",
        )
    )
    if launch.notes:
        note_text = "\n".join(f"  - {n}" for n in launch.notes)
        console.print(Panel(note_text, title="Launch notes", border_style="dim"))


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
        q_basis = c.provenance.get("quality", "unknown")
        q_mark = "" if q_basis == "measured" else "~"
        tp_basis = c.provenance.get("throughput", "unknown")
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
        _finite(
            {
                "considered": considered,
                "fit": len(ranked),
                "suggestions": [asdict(c) for c in ranked],
                "unresolved": [{"id": i, "error": m} for i, m in (errors or [])],
            }
        ),
        indent=2,
    )


def format_pareto(frontier: list[Candidate], hardware: str) -> None:
    """Render the Pareto frontier (cost / latency / quality trade-off menu)."""
    if not frontier:
        console.print(
            Panel(
                "[bold red]No viable configuration found.[/]",
                title="ChimeraForge Pareto Frontier",
                border_style="red",
            )
        )
        return

    cheapest = min(frontier, key=lambda c: c.monthly_cost)
    fastest = min(frontier, key=lambda c: c.p95_latency_ms)
    best_q = max(frontier, key=lambda c: c.quality)

    table = Table(title=f"Pareto frontier for {hardware} (non-dominated trade-offs)")
    table.add_column("Model")
    table.add_column("Quant")
    table.add_column("Backend")
    table.add_column("N", justify="right")
    table.add_column("Batch", justify="right")
    table.add_column("$/mo", justify="right")
    table.add_column("p95 ms", justify="right")
    table.add_column("Quality", justify="right")
    table.add_column("Pick", style="dim")

    for c in frontier:
        tags = []
        if c is cheapest:
            tags.append("cheapest")
        if c is fastest:
            tags.append("fastest")
        if c is best_q:
            tags.append("best-quality")
        q_mark = "" if c.provenance.get("quality") == "measured" else "~"
        table.add_row(
            c.model,
            c.quant,
            c.backend,
            str(c.n_agents),
            str(c.effective_batch),
            f"${c.monthly_cost}",
            f"{c.p95_latency_ms}",
            f"{q_mark}{c.quality}",
            ", ".join(tags),
        )
    console.print()
    console.print(table)
    console.print(
        f"  [dim]{len(frontier)} non-dominated configs. Each is best at *something* "
        f"(cost / latency / quality); points off the frontier are strictly worse.[/]\n"
    )


def format_pareto_json(frontier: list[Candidate]) -> str:
    """Pareto frontier as JSON."""
    return json.dumps(_finite([asdict(c) for c in frontier]), indent=2)


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


def format_api_comparison(cmp) -> None:
    """Print self-host vs hosted-API monthly cost and the break-even volume."""
    table = Table(
        title=f"Self-host vs hosted API  (workload: {cmp.requests_per_month:,.0f} req/mo, "
        f"{cmp.prompt_tokens} in / {cmp.output_tokens} out)"
    )
    table.add_column("Option")
    table.add_column("Class", style="dim")
    table.add_column("$/mo", justify="right")
    table.add_column("vs self-host", justify="right")
    table.add_column("Break-even out-tok/mo", justify="right")

    table.add_row(
        "[bold]self-host (this plan)[/]",
        "-",
        f"[bold green]${cmp.self_host_monthly:,.2f}[/]",
        "-",
        "-",
    )
    for o in cmp.options:
        verdict = "[green]self-host wins[/]" if o.self_host_cheaper else "[yellow]API wins[/]"
        be = f"{o.breakeven_tokens_month / 1e6:,.0f}M" if o.breakeven_tokens_month else "n/a"
        cls = "like-for-like" if o.model_class == "open" else o.model_class
        table.add_row(
            f"{o.name} [dim]({o.provider})[/]", cls, f"${o.monthly_cost:,.2f}", verdict, be
        )

    console.print()
    console.print(table)
    stale = (
        f"[red]STALE by {cmp.age_days} days[/] -- re-run scripts/build_cost_data.py"
        if cmp.stale
        else f"{cmp.age_days} days old"
    )
    console.print(
        f"  [dim]List prices captured {cmp.captured_at} ({stale}). "
        "Vendors publish no pricing API, so this is a dated snapshot, not a live quote.[/]"
    )
    console.print(
        "  [dim]'like-for-like' hosts the same class of open-weights model; 'frontier' is a "
        "different quality tier, so its price is not an apples-to-apples comparison.[/]\n"
    )


def format_fleet(plan) -> None:
    """Print a heterogeneous fleet allocation and what it saves over one GPU type."""
    title = "Heterogeneous fleet" if plan.is_mixed else "Fleet (single type was cheapest)"
    table = Table(
        title=f"{title}  (demand: {plan.demand_rate:g} req/s)",
        show_lines=False,
    )
    for col in ("GPU", "Units", "req/s each", "$/mo each", "$ per req/s", "Config"):
        table.add_column(col)
    for gpu, units in plan.units.items():
        if not units:
            continue
        o = plan.options[gpu]
        table.add_row(
            gpu,
            str(units),
            f"{o.rate_per_gpu:.2f}",
            f"${o.cost_per_gpu_month:,.2f}",
            f"${o.cost_per_rate:,.2f}",
            f"{o.quant}/{o.backend}",
        )
    console.print(table)

    console.print(
        f"  [bold]{plan.gpus_total} GPU(s)[/]  "
        f"[bold]${plan.monthly_cost:,.2f}/mo[/]  "
        f"serving {plan.served_rate:.2f} req/s of {plan.demand_rate:g} demanded"
    )
    if plan.best_homogeneous:
        gpu, units, cost = plan.best_homogeneous
        saved = plan.savings_vs_best_homogeneous
        if saved > 0:
            console.print(
                f"  [green]{saved:.1%} cheaper[/] than the best single type "
                f"({units} x {gpu}, ${cost:,.2f}/mo)"
            )
        else:
            # No saving is a real result, not a failure: say so rather than
            # leaving a mixed-fleet table implying one.
            console.print(
                f"  [dim]No saving over a single type[/] ({units} x {gpu}, "
                f"${cost:,.2f}/mo) -- homogeneous is already optimal here."
            )
    prov = plan.provenance()
    console.print(
        f"  [dim]provenance (worst across types used): "
        f"throughput={prov['throughput']}, quality={prov['quality']}[/]"
    )
    for warning in plan.warnings:
        console.print(f"  [yellow]![/] {escape(warning)}")
