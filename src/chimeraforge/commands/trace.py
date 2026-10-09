"""Execute a private request workload and emit only aggregate/hash-bound evidence."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import signal

import typer

from chimeraforge.bench.trace_workload import (
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_TRACE_TIMEOUT_SECONDS,
)


def trace(
    workload: Path = typer.Argument(
        ..., help="Private JSON request list; prompts go to the endpoint."
    ),
    model: str = typer.Option(..., "--model", help="Actually served model name."),
    backend: str = typer.Option("ollama", "--backend"),
    base_url: str | None = typer.Option(None, "--base-url"),
    concurrency: int = typer.Option(1, "--concurrency"),
    request_timeout: float = typer.Option(
        DEFAULT_REQUEST_TIMEOUT_SECONDS, "--request-timeout", help="Per-call timeout, seconds."
    ),
    trace_timeout: float = typer.Option(
        DEFAULT_TRACE_TIMEOUT_SECONDS, "--trace-timeout", help="Scheduled replay deadline, seconds."
    ),
    latency_slo: float | None = typer.Option(
        None, "--latency-slo", help="Queue-inclusive terminal latency, ms."
    ),
    first_output_slo: float | None = typer.Option(
        None, "--first-output-slo", help="Queue-inclusive first client output, ms."
    ),
    tpot_slo: float | None = typer.Option(
        None, "--tpot-slo", help="Explicitly labeled mean decode interval, ms/token."
    ),
    out: Path | None = typer.Option(
        None, "--out", help="Atomic receipt JSON; cannot replace the workload."
    ),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Replay real requests; completion exit 0 does not imply an SLO pass."""
    from chimeraforge import api
    from chimeraforge.plan_study import protect_output

    async def execute() -> api.TraceReplay:
        stopped = asyncio.Event()
        previous = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, lambda *_: stopped.set())
        try:
            return await api.replay_trace(
                workload,
                model=model,
                backend=backend,
                base_url=base_url,
                concurrency=concurrency,
                request_timeout=request_timeout,
                trace_timeout=trace_timeout,
                slos=api.TraceSLO(latency_slo, first_output_slo, tpot_slo),
                stop_event=stopped,
            )
        finally:
            signal.signal(signal.SIGINT, previous)

    try:
        if out is not None:
            protect_output(out, [workload])
        receipt = asyncio.run(execute())
        if out is not None:
            receipt.save(out)
        report = receipt.to_dict()
    except api.PlanError as exc:
        typer.echo(json.dumps({"error": str(exc)}) if json_output else str(exc))
        raise typer.Exit(2) from exc
    if json_output:
        typer.echo(json.dumps(report, allow_nan=False))
    else:
        typer.echo(
            f"Completed {report['execution']['completed']}/"
            f"{report['execution']['planned']} requests"
        )
        typer.echo(
            f"Joint-target goodput: {report['goodput']['requests_per_second']} requests/second"
        )
        typer.echo(report["limits"])
    raise typer.Exit(report["exit_code"])
