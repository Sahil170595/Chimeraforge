"""`report` command — generate benchmark reports from result files."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()


def report(
    results_dir: str = typer.Option(
        None,
        "--results-dir",
        "-d",
        help="Directory containing bench result JSON files.",
    ),
    results_files: str = typer.Option(
        None,
        "--results-files",
        "-f",
        help="Comma-separated paths to bench result JSON files.",
    ),
    fmt: str = typer.Option(
        "markdown",
        "--format",
        help="Output format: markdown or html.",
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path.",
    ),
    title: str = typer.Option(
        "ChimeraForge Benchmark Report",
        "--title",
        help="Report title.",
    ),
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Output report metadata as JSON.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable debug logging.",
    ),
) -> None:
    """Generate benchmark reports from result files."""
    import logging
    from pathlib import Path

    from chimeraforge.report.generator import (
        ReportConfig,
        format_report_rich,
        generate_report,
        load_results,
        save_report,
    )

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    # Collect result paths
    paths: list[Path] = []
    if results_dir:
        d = Path(results_dir)
        if not d.is_dir():
            console.print(f"[red]Error:[/] --results-dir '{results_dir}' is not a directory.")
            raise typer.Exit(code=1)
        paths.extend(sorted(d.glob("*.json")))
    if results_files:
        for f in results_files.split(","):
            p = Path(f.strip())
            if not p.is_file():
                console.print(f"[red]Error:[/] result file '{f.strip()}' not found.")
                raise typer.Exit(code=1)
            paths.append(p)

    if not paths:
        console.print("[red]Error:[/] provide --results-dir or --results-files.")
        raise typer.Exit(code=1)

    if fmt not in ("markdown", "html"):
        console.print("[red]Error:[/] --format must be 'markdown' or 'html'.")
        raise typer.Exit(code=1)

    config = ReportConfig(title=title, format=fmt)
    try:
        results = load_results(paths)
    except (FileNotFoundError, ValueError) as exc:  # ValueError covers JSONDecodeError
        console.print(f"[red]Error:[/] failed to read result file(s): {exc}")
        raise typer.Exit(code=1)

    if not any(isinstance(r, dict) and "model" in r for r in results):
        console.print(
            "[red]Error:[/] no valid bench results found "
            "(expected JSON objects with a 'model' field)."
        )
        raise typer.Exit(code=1)

    rpt = generate_report(paths, config)

    if output:
        out_path = Path(output)
        saved = save_report(rpt, out_path)
        console.print(f"[green]Report saved to:[/] {saved}")
    elif output_json:
        import json as json_mod

        meta = {
            "title": rpt.title,
            "format": rpt.format,
            "n_results": rpt.n_results,
            "timestamp": rpt.timestamp,
        }
        console.print(json_mod.dumps(meta, indent=2))
    else:
        format_report_rich(results, console)
