"""`workload` command - derive plan inputs from real traffic."""

from __future__ import annotations

import json as json_mod
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

console = Console()
err_console = Console(stderr=True)


def _fail(message: str) -> None:
    err_console.print(f"[red]Error:[/] {message}")
    raise typer.Exit(code=1)


def workload(
    from_log: str = typer.Option(
        None,
        "--from-log",
        metavar="PATH",
        help="JSONL request log, one JSON object per request. The exact path: real "
        "per-request token counts give a measured distribution, not a bucket "
        "approximation.",
    ),
    from_metrics: str = typer.Option(
        None,
        "--from-metrics",
        metavar="URL_OR_PATH",
        help="A live /metrics endpoint (http...) or a saved scrape. Requires --engine.",
    ),
    engine: str = typer.Option(
        None,
        "--engine",
        help="Which engine produced the metrics: vllm or sglang. Required with "
        "--from-metrics -- metric names differ per engine and per version, and "
        "guessing one fabricates a measurement.",
    ),
    engine_version: str = typer.Option(
        "unknown",
        "--engine-version",
        help="Engine version, recorded in the profile so a later reader knows which "
        "metric names it was read with.",
    ),
    out: str = typer.Option(
        None,
        "--out",
        "-o",
        metavar="PATH",
        help="Write the profile as JSON to PATH (for `plan --workload-profile`).",
    ),
    output_json: bool = typer.Option(False, "--json", help="Print the profile as JSON."),
) -> None:
    """Derive plan inputs (rate, token lengths, variance, cache hit rate) from traffic.

    `plan` otherwise takes all of these as typed-in guesses -- including the traffic
    variance that drives the whole queueing tail. Whatever is serving your traffic
    already measures them.
    """
    from chimeraforge.workload import (
        WorkloadError,
        fetch_metrics,
        format_markdown,
    )
    from chimeraforge.workload import (
        from_log as derive_from_log,
    )
    from chimeraforge.workload import (
        from_metrics as derive_from_metrics,
    )

    if bool(from_log) == bool(from_metrics):
        _fail("pass exactly one of --from-log or --from-metrics.")
    if from_metrics and not engine:
        _fail("--from-metrics needs --engine (vllm or sglang).")

    try:
        if from_log:
            profile = derive_from_log(from_log, engine=engine or "unknown")
        else:
            if from_metrics.startswith(("http://", "https://")):
                text = fetch_metrics(from_metrics)
            else:
                try:
                    text = Path(from_metrics).read_text(encoding="utf-8")
                except OSError as exc:
                    _fail(f"could not read {escape(from_metrics)}: {exc}")
            profile = derive_from_metrics(
                text, engine=engine, source=from_metrics, engine_version=engine_version
            )
    except WorkloadError as exc:
        _fail(escape(str(exc)))

    if out:
        try:
            Path(out).write_text(
                json_mod.dumps(profile.to_dict(), indent=2) + "\n", encoding="utf-8"
            )
        except OSError as exc:
            _fail(f"could not write {escape(out)}: {exc}")

    if output_json:
        console.print(json_mod.dumps(profile.to_dict(), indent=2), highlight=False, soft_wrap=True)
        return

    console.print(format_markdown(profile).split("| Field")[0])
    table = Table(title="Derived inputs", show_lines=False)
    for col in ("Field", "Value", "Provenance", "How"):
        table.add_column(col)
    any_row = False
    for name in (
        "request_rate",
        "prompt_tokens",
        "output_tokens",
        "workload_cv2",
        "prefix_cache_hit_rate",
        "peak_concurrency",
        "queue_depth",
    ):
        f = getattr(profile, name)
        if f is not None:
            any_row = True
            colour = "green" if f.provenance == "measured" else "yellow"
            table.add_row(name, str(f.value), f"[{colour}]{f.provenance}[/]", f.note)
    if any_row:
        console.print(table)
    if profile.absent:
        console.print("\n[bold]Not measured[/] (still required explicitly by `plan`):")
        for a in profile.absent:
            console.print(f"  [yellow]-[/] {a}")
    for n in profile.notes:
        console.print(f"  [dim]note:[/] {n}")
    if out:
        console.print(f"\n[green]Profile written to[/] [bold]{escape(out)}[/]")
        console.print(f"[dim]Use it:[/] chimeraforge plan --workload-profile {escape(out)} ...")
