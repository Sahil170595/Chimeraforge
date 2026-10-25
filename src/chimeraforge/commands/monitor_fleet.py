"""Observe every explicitly declared saved replica without generating traffic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import signal

import typer

from chimeraforge.fleet_monitor_types import FleetMonitorReport


def monitor_fleet(
    from_plan: Path = typer.Option(..., "--from-plan", help="Original saved plan."),
    endpoint: list[str] = typer.Option(
        ..., "--endpoint", help="Repeat ID=URL once per saved replica."
    ),
    candidate_index: int = typer.Option(0, "--candidate-index"),
    ttft_slo: float | None = typer.Option(
        None, "--ttft-slo", help="Override saved TTFT target, ms."
    ),
    tpot_slo: float | None = typer.Option(
        None, "--tpot-slo", help="Override saved TPOT target, ms."
    ),
    interval: float = typer.Option(30.0, "--interval"),
    windows: int = typer.Option(1, "--windows"),
    timeout: float = typer.Option(10.0, "--timeout"),
    observation_seconds: float = typer.Option(60.0, "--observation-seconds"),
    cleanup_seconds: float = typer.Option(2.0, "--cleanup-seconds"),
    concurrency: int = typer.Option(4, "--concurrency"),
    max_requests: int = typer.Option(256, "--max-requests"),
    max_body_bytes: int = typer.Option(8 * 1024 * 1024, "--max-body-bytes"),
    output_json: bool = typer.Option(False, "--json"),
    prometheus: Path | None = typer.Option(None, "--prometheus"),
) -> None:
    """Passively qualify declared coverage: pass0, breach3, unknown4, mismatch5."""
    from chimeraforge.api import PlanError, monitor_fleet as observe
    from chimeraforge.fleet_monitor import (
        MAX_ENDPOINTS,
        MAX_ID_CHARS,
        MAX_URL_CHARS,
        FleetEndpoint,
        FleetMonitorError,
        FleetMonitorRequest,
        write_prometheus,
    )
    from chimeraforge.plan_study import protect_output

    async def operation(request: FleetMonitorRequest) -> FleetMonitorReport:
        stop = asyncio.Event()
        previous = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, lambda *_: stop.set())
        try:
            return await observe(
                from_plan, request, candidate_index=candidate_index, stop_event=stop
            )
        finally:
            signal.signal(signal.SIGINT, previous)

    try:
        if len(endpoint) > MAX_ENDPOINTS:
            raise FleetMonitorError("at most 16 endpoint declarations are admitted")
        values = []
        for declaration in endpoint:
            if len(declaration) > MAX_ID_CHARS + 1 + MAX_URL_CHARS or "=" not in declaration:
                raise FleetMonitorError("endpoint must be bounded ID=URL")
            name, url = declaration.split("=", 1)
            values.append(FleetEndpoint(name, url))
        if prometheus is not None:
            protect_output(prometheus, (from_plan,))
        request = FleetMonitorRequest(
            tuple(values),
            interval,
            windows,
            timeout,
            observation_seconds,
            cleanup_seconds,
            concurrency,
            max_requests,
            max_body_bytes,
            ttft_slo,
            tpot_slo,
        )
        report = asyncio.run(operation(request))
        if prometheus is not None:
            write_prometheus(report, prometheus)
    except (FleetMonitorError, PlanError, OSError, ValueError):
        if output_json:
            typer.echo(
                json.dumps({"error": "invalid, unsupported or unavailable fleet observation"})
            )
        else:
            typer.echo("Error: invalid, unsupported or unavailable fleet observation", err=True)
        raise typer.Exit(1) from None
    if output_json:
        typer.echo(json.dumps(report.to_dict(), indent=2, allow_nan=False))
    else:
        data = report.to_dict()
        typer.echo(
            f"Declared fleet: {data['outcome']}; "
            f"{data['declared_coverage']['complete']}/{len(report.slots)} complete"
        )
        for slot in report.slots:
            typer.echo(
                f"  {slot.id}: {slot.state}; SLO {slot.slo}; "
                f"identity {slot.binding['identity']['state']}"
            )
    raise typer.Exit(report.exit_code)
