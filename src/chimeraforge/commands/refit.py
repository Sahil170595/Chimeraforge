"""`refit` command - re-fit planner coefficients from benchmark results."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()
# Diagnostics here so `--json` stdout stays exactly one document. A caller that
# must strip lines before parsing does not have a contract.
err_console = Console(stderr=True)


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
            err_console.print(f"[red]Error:[/] --bench-dir '{bench_dir}' is not a directory.")
            raise typer.Exit(code=1)
        paths.extend(sorted(d.glob("*.json")))
    if bench_files:
        for f in bench_files.split(","):
            p = Path(f.strip())
            if not p.is_file():
                err_console.print(f"[red]Error:[/] bench file '{f.strip()}' not found.")
                raise typer.Exit(code=1)
            paths.append(p)

    if not paths:
        err_console.print("[red]Error:[/] provide --bench-dir or --bench-files.")
        raise typer.Exit(code=1)

    from chimeraforge.planner.resolver import measured_corpus_path

    if base_models:
        base_path = Path(base_models)
    else:
        # Accumulate onto the measured corpus when one exists, which is what
        # `measure` does. Basing on the bundled snapshot while WRITING to the
        # measured path meant a refit silently deleted every row `measure` had
        # accumulated -- throughput rows and serial fractions both -- with no
        # warning, no backup and exit 0. The two commands share a file, so they
        # must share its merge semantics.
        existing = Path(measured_corpus_path())
        base_path = existing if existing.is_file() else None
    try:
        merged, summary = refit_from_bench(paths, base_path)
    except (FileNotFoundError, ValueError) as exc:  # ValueError covers JSONDecodeError
        err_console.print(f"[red]Error:[/] failed to read bench file(s): {exc}")
        raise typer.Exit(code=1)

    # Determine output path
    if output:
        out = Path(output)
    else:
        # The one path plan/suggest/MCP actually read, honouring $CHIMERAFORGE_CACHE.
        # This used to default to platformdirs' user_data_dir while the read side
        # used ~/.cache/chimeraforge, so a successful refit printed "Saved to ..."
        # and exited 0 while being completely inert.
        out = Path(measured_corpus_path())

    # Validate BEFORE writing so --validate is a real gate, not advisory: invalid
    # coefficients (e.g. a quant multiplier < FP16, non-positive throughput) must
    # never be persisted with a misleading non-zero exit implying nothing was saved.
    vresult = None
    if validate:
        from chimeraforge.refit.validator import (
            format_validation_json,
            format_validation_table,
            validate_fitted_models,
        )

        vresult = validate_fitted_models(merged)
        if not vresult.passed:
            if output_json:
                # highlight=False + soft_wrap: valid JSON for `--json | jq`.
                console.print(format_validation_json(vresult), highlight=False, soft_wrap=True)
            else:
                format_validation_table(vresult, console)
                err_console.print("[red]Validation failed -- refit NOT saved.[/]")
            raise typer.Exit(code=1)

    saved = save_fitted_models(merged, out)

    if output_json:
        console.print(json_mod.dumps(summary, indent=2), highlight=False, soft_wrap=True)
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

    if validate and vresult is not None:
        from chimeraforge.refit.validator import format_validation_json, format_validation_table

        if output_json:
            # stderr: the summary above is already the one stdout document, and
            # emitting this there produced two concatenated JSON objects that no
            # parser accepts.
            err_console.print(format_validation_json(vresult), highlight=False, soft_wrap=True)
        else:
            format_validation_table(vresult, console)
