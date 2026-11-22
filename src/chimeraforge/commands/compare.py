"""`compare` command - diff benchmark results between runs."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()


def compare(
    baseline: str = typer.Option(
        ...,
        "--baseline",
        "-b",
        help="Path to baseline bench result JSON.",
    ),
    candidate: str = typer.Option(
        ...,
        "--candidate",
        "-c",
        help="Path(s) to candidate bench result JSON (comma-separated).",
    ),
    output_json: bool = typer.Option(
        False,
        "--json",
        help="Output matched rows as a flat JSON array.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable debug logging.",
    ),
    grouped_json: bool = typer.Option(
        False,
        "--grouped-json",
        help="Output JSON grouped by candidate, including unmatched configurations.",
    ),
) -> None:
    """Compare benchmark results between runs."""
    import logging
    from pathlib import Path

    from chimeraforge.compare.comparator import (
        compare_candidates,
        format_candidate_groups_json,
        format_comparison_json,
        format_comparison_summary,
        format_comparison_table,
    )

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    if output_json and grouped_json:
        typer.echo("Error: --json and --grouped-json are mutually exclusive.", err=True)
        raise typer.Exit(code=1)

    baseline_path = Path(baseline)
    if not baseline_path.is_file():
        console.print(f"[red]Error:[/] baseline file '{baseline}' not found.")
        raise typer.Exit(code=1)

    candidate_paths: list[Path] = []
    for c in candidate.split(","):
        p = Path(c.strip())
        if not p.is_file():
            console.print(f"[red]Error:[/] candidate file '{c.strip()}' not found.")
            raise typer.Exit(code=1)
        candidate_paths.append(p)

    try:
        comparisons = compare_candidates(baseline_path, candidate_paths)
    except (OSError, ValueError) as exc:
        typer.echo(f"Error: failed to read result file(s): {exc}", err=True)
        raise typer.Exit(code=1)

    if grouped_json:
        typer.echo(format_candidate_groups_json(baseline_path, comparisons))
        return
    if output_json:
        typer.echo(format_comparison_json([row for group in comparisons for row in group.rows]))
        return

    for group in comparisons:
        console.print(f"Candidate: {group.candidate}", markup=False)
        format_comparison_table(group.rows, console)
        format_comparison_summary(group.rows, console)
        if group.baseline_only or group.candidate_only:
            console.print(
                f"Baseline-only configurations: {len(group.baseline_only)}. "
                f"Candidate-only configurations: {len(group.candidate_only)}."
            )
