"""`report` command - generate benchmark reports from result files."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()


def _defaulted(ctx: typer.Context, name: str) -> bool:
    source = ctx.get_parameter_source(name)
    return source is not None and source.name == "DEFAULT"


def report(
    ctx: typer.Context,
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
        help="markdown or html; trace modes also support svg.",
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
    kind: str = typer.Option(
        "benchmark",
        "--kind",
        help=(
            "benchmark, trace, fleet-trace, trace-campaign, fleet-trace-campaign or fleet-monitor."
        ),
    ),
    input_path: list[str] = typer.Option(
        None, "--input", help="One complete native trace, campaign or passive fleet receipt."
    ),
    plan_path: list[str] = typer.Option(
        None, "--plan", help="Original saved plan (fleet-monitor only)."
    ),
    candidate_index: int | None = typer.Option(
        None, "--candidate-index", help="Original plan candidate (fleet-monitor only, default 0)."
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

    passive = kind == "fleet-monitor"
    if not passive and (plan_path or candidate_index is not None):
        typer.echo("--plan and --candidate-index apply only to fleet-monitor reports.", err=True)
        raise typer.Exit(code=2)
    if kind != "benchmark":
        from chimeraforge import api

        legacy_selectors = any(
            not _defaulted(ctx, name) for name in ("results_dir", "results_files")
        )
        if (
            kind
            not in {
                "trace",
                "fleet-trace",
                "trace-campaign",
                "fleet-trace-campaign",
                "fleet-monitor",
            }
            or not input_path
            or len(input_path) != 1
            or legacy_selectors
            or output_json
            or (passive and (not plan_path or len(plan_path) != 1))
        ):
            message = (
                "Fleet monitor report requires one --input and one --plan, "
                "with no benchmark selectors/--json."
                if passive
                else "Trace report requires one --input and no benchmark selectors/--json."
            )
            typer.echo(message, err=True)
            raise typer.Exit(code=2)
        try:
            if passive:
                artifact = api.render_fleet_monitor_report(
                    input_path[0],
                    plan_path[0],
                    candidate_index=0 if candidate_index is None else candidate_index,
                    format=fmt,
                    title="Passive fleet diagnostics" if _defaulted(ctx, "title") else title,
                )
            else:
                artifact = api.render_trace_report(
                    input_path[0],
                    kind=kind,
                    format=fmt,
                    title="Trace diagnostics" if _defaulted(ctx, "title") else title,
                )
            if output:
                artifact.save(output)
            typer.echo(artifact.content.encode("utf-8"), nl=False)
        except api.PlanError:
            label = "Fleet monitor report" if passive else "Trace report"
            typer.echo(f"{label} input or output unavailable.", err=True)
            raise typer.Exit(code=2) from None
        return
    if input_path:
        typer.echo("Benchmark reports use --results-dir or --results-files.", err=True)
        raise typer.Exit(code=2)

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
        # highlight=False + soft_wrap: valid JSON for `--json | jq`.
        console.print(json_mod.dumps(meta, indent=2), highlight=False, soft_wrap=True)
    else:
        format_report_rich(results, console)
