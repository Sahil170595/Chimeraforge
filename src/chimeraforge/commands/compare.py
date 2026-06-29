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
        help="Output as JSON.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable debug logging.",
    ),
) -> None:
    """Compare benchmark results between runs."""
    import logging
    from pathlib import Path

    from chimeraforge.compare.comparator import (
        compare_results,
        format_comparison_json,
        format_comparison_summary,
        format_comparison_table,
    )

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

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
        rows = compare_results(baseline_path, candidate_paths)
    except (FileNotFoundError, ValueError) as exc:  # ValueError covers JSONDecodeError
        console.print(f"[red]Error:[/] failed to read result file(s): {exc}")
        raise typer.Exit(code=1)

    if output_json:
        # highlight=False + soft_wrap: valid JSON for `--json | jq` (Rich otherwise
        # reflows long values at width 79 when piped and corrupts them).
        console.print(format_comparison_json(rows), highlight=False, soft_wrap=True)
    else:
        format_comparison_table(rows, console)
        format_comparison_summary(rows, console)
