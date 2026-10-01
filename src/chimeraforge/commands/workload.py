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
    from_metrics: list[str] = typer.Option(
        None,
        "--from-metrics",
        metavar="URL_OR_PATH",
        help="A live /metrics endpoint (http...) or a saved scrape. Requires --engine. "
        "Pass it twice (two saved scrapes, with --interval) for a window.",
    ),
    interval: float = typer.Option(
        None,
        "--interval",
        metavar="SECONDS",
        help="Make a window: with a URL, scrape twice this far apart (the real gap is "
        "timed); with two saved scrapes, the gap between them. A window measures the "
        "request rate and, with --hardware, MFU/MBU.",
    ),
    hardware: str = typer.Option(
        None,
        "--hardware",
        help="The GPU the engine runs on (a hardware DB name), for MFU/MBU from the "
        "engine's FLOP/byte counters over a window.",
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
        PROFILE_FIELDS,
        WorkloadError,
        fetch_metrics,
        format_markdown,
        from_metrics_window,
        scrape_window,
    )
    from chimeraforge.workload import (
        from_log as derive_from_log,
    )
    from chimeraforge.workload import (
        from_metrics as derive_from_metrics,
    )

    sources = list(from_metrics or [])
    if bool(from_log) == bool(sources):
        _fail("pass exactly one of --from-log or --from-metrics.")
    if sources and not engine:
        _fail("--from-metrics needs --engine (vllm or sglang).")
    if from_log and (interval is not None or hardware):
        _fail("--interval and --hardware apply to --from-metrics.")
    if len(sources) > 2:
        _fail("--from-metrics takes at most two scrapes (the start and end of a window).")
    is_url = [s.startswith(("http://", "https://")) for s in sources]
    if len(sources) == 2:
        if interval is None:
            _fail("two saved scrapes need --interval: the seconds between them.")
        if any(is_url):
            _fail(
                "two saved scrapes must be files; for a live endpoint pass one URL "
                "with --interval and it is scraped twice."
            )
    if len(sources) == 1 and interval is not None and not is_url[0]:
        _fail(
            "--interval with one saved file has nothing to difference: pass two saved "
            "scrapes (--from-metrics twice), or a live URL."
        )
    if interval is not None and interval <= 0:
        _fail("--interval must be a positive number of seconds.")
    gpu = None
    if hardware:
        from chimeraforge.planner.hardware import get_gpu

        gpu = get_gpu(hardware)
        if gpu is None:
            _fail(
                f"'{escape(hardware)}' is not in the hardware DB; run "
                "`chimeraforge plan --list-hardware` for the names."
            )

    def _read(path: str) -> str:
        try:
            return Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            _fail(f"could not read {escape(path)}: {exc}")

    try:
        if from_log:
            profile = derive_from_log(from_log, engine=engine or "unknown")
        elif len(sources) == 2:
            profile = from_metrics_window(
                _read(sources[0]),
                _read(sources[1]),
                interval,
                engine=engine,
                source=f"{sources[0]} -> {sources[1]}",
                engine_version=engine_version,
                gpu=gpu,
            )
        elif interval is not None:
            profile = scrape_window(
                sources[0], interval, engine=engine, engine_version=engine_version, gpu=gpu
            )
        else:
            text = fetch_metrics(sources[0]) if is_url[0] else _read(sources[0])
            profile = derive_from_metrics(
                text, engine=engine, source=sources[0], engine_version=engine_version
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
    for name in PROFILE_FIELDS:
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
