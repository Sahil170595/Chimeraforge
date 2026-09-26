"""`doctor` command - read-only check of the local GPU platform.

Reports what each vendor's tool found, what the planner can do with each device
today, and which serving engines identify themselves on their default ports.
Changes nothing. (`check` is reserved for plan drift detection.)
"""

from __future__ import annotations

import json as json_mod

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

console = Console()

_STATUS_STYLE = {"matched": "green", "supply-figures": "yellow", "not-representable": "red"}
_SUPPORT_STYLE = {
    "supported": "green",
    "experimental": "yellow",
    "unsupported": "red",
    "not documented": "dim",
}


def doctor(
    output_json: bool = typer.Option(False, "--json", help="Print the report as JSON."),
    no_engines: bool = typer.Option(
        False, "--no-engines", help="Skip probing local serving engines."
    ),
) -> None:
    """Check this machine: detected GPUs, what the planner can model, local engines."""
    from chimeraforge.doctor import run_doctor

    report = run_doctor(check_engines=not no_engines)

    if output_json:
        console.print(json_mod.dumps(report.to_dict(), indent=2), highlight=False, soft_wrap=True)
        return

    wsl = " (WSL)" if report.wsl else ""
    where = f"{report.os} {report.os_version}{wsl} {report.arch}"
    console.print(f"[bold]Platform[/] {escape(where)}")

    probes = Table(title="Detection")
    probes.add_column("Tool")
    probes.add_column("Found")
    probes.add_column("Detail")
    probes.add_column("Runtime")
    for p in report.probes:
        runtime = ", ".join(f"{k} {v}" for k, v in p.runtime.items())
        probes.add_row(p.tool, "yes" if p.found else "no", escape(p.detail), escape(runtime))
    console.print(probes)

    if report.gpus:
        planner = Table(title="What the planner can do")
        planner.add_column("GPU")
        planner.add_column("VRAM")
        planner.add_column("Status")
        planner.add_column("Detail")
        by_name = {s.gpu: s for s in report.planner}
        for g in report.gpus:
            s = by_name[g.name]
            vram = f"{g.vram_gb:g} GB" if g.vram_gb else "unknown"
            style = _STATUS_STYLE.get(s.status, "white")
            planner.add_row(escape(g.name), vram, f"[{style}]{s.status}[/]", escape(s.detail))
        console.print(planner)

    if report.engine_support:
        matrix = Table(title="Engine support here (each engine's own docs)")
        matrix.add_column("Platform")
        matrix.add_column("Engine")
        matrix.add_column("Status")
        matrix.add_column("Scope / note")
        for s in report.engine_support:
            style = _SUPPORT_STYLE.get(s["status"], "white")
            note = s["scope"] or ""
            if s["maintenance"]:
                note = (note + "; " if note else "") + "maintenance mode (repo archived)"
            matrix.add_row(
                s["platform"],
                f"{s['engine']} {s['engine_version']}",
                f"[{style}]{s['status']}[/]",
                escape(note),
            )
        console.print(matrix)
        console.print("  [dim]Quotes and pinned source URLs are in `doctor --json`.[/]")

    if report.engines:
        engines = Table(title="Local serving engines")
        engines.add_column("Engine")
        engines.add_column("URL")
        engines.add_column("Running")
        engines.add_column("Detail")
        for e in report.engines:
            state = f"yes ({e.version})" if e.running else "no"
            engines.add_row(e.backend, e.url, state, escape(e.detail))
        console.print(engines)

    for note in report.notes:
        console.print(f"[yellow]note:[/] {escape(note)}")
