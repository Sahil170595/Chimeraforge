"""Execute a serial campaign with a frozen private workload and complete receipts."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import signal

import typer

from chimeraforge.bench.trace_campaign import (
    DEFAULT_CAMPAIGN_TIMEOUT_SECONDS,
    DEFAULT_REPLICATES,
)
from chimeraforge.bench.trace_workload import (
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_TRACE_TIMEOUT_SECONDS,
)


def trace_campaign(
    workload: Path = typer.Argument(..., help="Private JSON workload; prompts go to the endpoint."),
    model: str = typer.Option(..., "--model", help="Actually served model name."),
    backend: str = typer.Option("ollama", "--backend"),
    base_url: str | None = typer.Option(None, "--base-url"),
    replicates: int = typer.Option(
        DEFAULT_REPLICATES, "--replicates", help="Serial replicas, 1-16."
    ),
    concurrency: int = typer.Option(1, "--concurrency"),
    request_timeout: float = typer.Option(
        DEFAULT_REQUEST_TIMEOUT_SECONDS, "--request-timeout", help="Per-call timeout, seconds."
    ),
    trace_timeout: float = typer.Option(
        DEFAULT_TRACE_TIMEOUT_SECONDS,
        "--trace-timeout",
        help="Each scheduled replay deadline, seconds.",
    ),
    campaign_timeout: float = typer.Option(
        DEFAULT_CAMPAIGN_TIMEOUT_SECONDS,
        "--campaign-timeout",
        help="Whole admission/preflight/metadata/replay budget; drain is cooperative.",
    ),
    latency_slo: float | None = typer.Option(
        None, "--latency-slo", help="Queue-inclusive latency, ms."
    ),
    first_output_slo: float | None = typer.Option(
        None, "--first-output-slo", help="First output, ms."
    ),
    tpot_slo: float | None = typer.Option(
        None, "--tpot-slo", help="Labeled mean decode, ms/token."
    ),
    out: Path | None = typer.Option(
        None, "--out", help="Atomic campaign JSON; protects the workload."
    ),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Serial native execution; exit 0 complete, 1 incomplete/stopped, 2 malformed/output."""
    from chimeraforge import api
    from chimeraforge.plan_study import protect_output

    async def execute() -> api.TraceCampaign:
        stopped = asyncio.Event()
        previous = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, lambda *_: stopped.set())
        try:
            return await api.replay_trace_campaign(
                workload,
                model=model,
                backend=backend,
                base_url=base_url,
                replicates=replicates,
                concurrency=concurrency,
                request_timeout=request_timeout,
                trace_timeout=trace_timeout,
                campaign_timeout=campaign_timeout,
                slos=api.TraceSLO(latency_slo, first_output_slo, tpot_slo),
                stop_event=stopped,
            )
        finally:
            signal.signal(signal.SIGINT, previous)

    try:
        if out is not None:
            protect_output(out, [workload])
        result = asyncio.run(execute())
        if out is not None:
            result.save(out)
        report = result.to_dict()
    except api.PlanError as exc:
        typer.echo(json.dumps({"error": str(exc)}) if json_output else str(exc))
        raise typer.Exit(2) from exc
    if json_output:
        typer.echo(json.dumps(report, allow_nan=False))
    else:
        typer.echo(
            f"Completed {report['execution']['completed']}/"
            f"{report['execution']['planned']} replicas"
        )
        typer.echo(report["limits"])
    raise typer.Exit(report["exit_code"])
