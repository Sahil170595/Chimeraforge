"""`refit` command — re-fit planner coefficients from benchmark results."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()


def refit(
    bench_dir: str = typer.Option(
        None,
        "--bench-dir",
        "-d",
        help="Directory containing bench result JSON files.",
    ),
    bench_files: str = typer.Option(
        None,
        "--bench-files",
        "-f",
        help="Comma-separated paths to bench JSON files.",
    ),
    base_models: str = typer.Option(
        None,
        "--base-models",
        help="Path to base fitted_models.json (default: bundled).",
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path for updated fitted_models.json.",
    ),
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Output summary as JSON.",
    ),
    validate: bool = typer.Option(
        False,
        "--validate",
        help="Run validation checks on the refitted model.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable debug logging.",
    ),
) -> None:
    """Re-fit planner coefficients from benchmark results."""
    import json as json_mod
    import logging
    from pathlib import Path

    from rich.panel import Panel

    from chimeraforge.refit.fitter import refit_from_bench, save_fitted_models

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    # Collect bench paths
    paths: list[Path] = []
    if bench_dir:
        d = Path(bench_dir)
        if not d.is_dir():
            console.print(f"[red]Error:[/] --bench-dir '{bench_dir}' is not a directory.")
            raise typer.Exit(code=1)
        paths.extend(sorted(d.glob("*.json")))
    if bench_files:
        for f in bench_files.split(","):
            p = Path(f.strip())
            if not p.is_file():
                console.print(f"[red]Error:[/] bench file '{f.strip()}' not found.")
                raise typer.Exit(code=1)
            paths.append(p)

    if not paths:
        console.print("[red]Error:[/] provide --bench-dir or --bench-files.")
        raise typer.Exit(code=1)

    base_path = Path(base_models) if base_models else None
    merged, summary = refit_from_bench(paths, base_path)

    # Determine output path
    if output:
        out = Path(output)
    else:
        try:
            from platformdirs import user_data_dir

            out = Path(user_data_dir("chimeraforge")) / "fitted_models.json"
        except ImportError:
            out = Path.home() / ".chimeraforge" / "fitted_models.json"

    saved = save_fitted_models(merged, out)

    if output_json:
        console.print(json_mod.dumps(summary, indent=2))
    else:
        lines = [
            f"Bench results loaded: {summary['bench_results_loaded']}",
            f"Throughput entries updated: {summary['throughput_entries_updated']}",
            f"Quant multipliers updated: {summary['quant_multipliers_updated']}",
            f"Service times updated: {summary['service_times_updated']}",
            f"Power law re-fit: {summary['power_law_refit']}",
        ]
        if summary.get("warnings"):
            lines.append("")
            for w in summary["warnings"]:
                lines.append(f"[yellow]Warning:[/] {w}")
        console.print(Panel("\n".join(lines), title="Refit Summary", border_style="green"))
        console.print(f"[green]Saved to:[/] {saved}")

    if validate:
        from chimeraforge.refit.validator import (
            format_validation_json,
            format_validation_table,
            validate_fitted_models,
        )

        vresult = validate_fitted_models(merged)
        if output_json:
            console.print(format_validation_json(vresult))
        else:
            format_validation_table(vresult, console)
        if not vresult.passed:
            raise typer.Exit(code=1)
