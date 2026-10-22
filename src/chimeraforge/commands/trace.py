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
    model: str | None = typer.Option(
        None, "--model", help="Served model; required without --from-plan."
    ),
    backend: str | None = typer.Option(
        None, "--backend", help="Backend (default ollama); omit with --from-plan."
    ),
    from_plan: Path | None = typer.Option(
        None, "--from-plan", help="Frozen saved plan or verified portable bundle."
    ),
    candidate_index: int | None = typer.Option(
        None, "--candidate-index", help="Saved candidate index; requires --from-plan (default 0)."
    ),
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

    async def execute() -> api.TraceReplay | api.PlanTraceReplay:
        stopped = asyncio.Event()
        previous = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, lambda *_: stopped.set())
        try:
            if from_plan is not None:
                from chimeraforge.bench.plan_trace import _prepare, _replay_prepared

                prepared = _prepare(
                    from_plan,
                    workload,
                    candidate_index=0 if candidate_index is None else candidate_index,
                    model=model,
                    base_url=base_url,
                    concurrency=concurrency,
                    request_timeout=request_timeout,
                    trace_timeout=trace_timeout,
                    stop_event=stopped,
                )
                if out is not None:
                    protect_output(out, prepared.protected_paths)
                return await _replay_prepared(prepared)
            assert model is not None  # Ordinary mode was admitted before creating the event loop.
            return await api.replay_trace(
                workload,
                model=model,
                backend="ollama" if backend is None else backend,
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
        if from_plan is None:
            if candidate_index is not None:
                raise api.PlanError("--candidate-index requires --from-plan")
            if model is None or not model.strip():
                raise api.PlanError("--model is required without --from-plan")
        else:
            if backend is not None:
                raise api.PlanError("--backend cannot override a saved --from-plan candidate")
            if any(value is not None for value in (latency_slo, first_output_slo, tpot_slo)):
                raise api.PlanError("explicit SLO flags cannot override saved --from-plan inputs")
        if out is not None:
            protect_output(out, [workload, *([from_plan] if from_plan is not None else [])])
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
        native = report["native_trace"] if from_plan is not None else report
        typer.echo(
            f"Completed {native['execution']['completed']}/"
            f"{native['execution']['planned']} requests"
        )
        typer.echo(
            f"Joint-target goodput: {native['goodput']['requests_per_second']} requests/second"
        )
        typer.echo(report["limits"])
    raise typer.Exit(report["exit_code"])
