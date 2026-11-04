"""Continuous fixed fleet observations; the listener never polls on a scrape."""

from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path
import signal

import typer


def monitor_fleet_exporter(
    from_plan: Path = typer.Option(..., "--from-plan"),
    endpoint: list[str] = typer.Option(
        ..., "--endpoint", help="Repeat one original ID=URL per replica."
    ),
    candidate_index: int = typer.Option(0, "--candidate-index"),
    listen_host: str = typer.Option("127.0.0.1", "--listen-host"),
    listen_port: int = typer.Option(9400, "--listen-port"),
    poll_seconds: float = typer.Option(
        15.0, "--poll-seconds", help="Pause after each completed native poll."
    ),
    stale_after_seconds: float = typer.Option(60.0, "--stale-after-seconds"),
    max_clients: int = typer.Option(16, "--max-clients"),
    run_seconds: float | None = typer.Option(
        None, "--run-seconds", help="Optional bounded run; default is continuous."
    ),
    interval: float = typer.Option(30.0, "--interval", help="Native two-scrape sampling interval."),
    timeout: float = typer.Option(10.0, "--timeout"),
    observation_seconds: float = typer.Option(60.0, "--observation-seconds"),
    cleanup_seconds: float = typer.Option(2.0, "--cleanup-seconds"),
    concurrency: int = typer.Option(4, "--concurrency"),
    max_requests: int = typer.Option(256, "--max-requests"),
    max_body_bytes: int = typer.Option(8 * 1024 * 1024, "--max-body-bytes"),
    ttft_slo: float | None = typer.Option(None, "--ttft-slo"),
    tpot_slo: float | None = typer.Option(None, "--tpot-slo"),
    secure: bool = typer.Option(False, "--secure"),
    bearer_env: list[str] | None = typer.Option(None, "--bearer-env"),
    ca_bundle: list[str] | None = typer.Option(None, "--ca-bundle"),
    client_cert: list[str] | None = typer.Option(None, "--client-cert"),
    client_key: list[str] | None = typer.Option(None, "--client-key"),
) -> None:
    """Serve cached ordinal-labelled gauges; clean exit0 is not fleet qualification."""
    from chimeraforge import api
    from chimeraforge.fleet_monitor_types import (
        FleetEndpoint,
        FleetMonitorRequest,
        MAX_ENDPOINTS,
        MAX_URL_CHARS,
        MAX_ID_CHARS,
    )
    from chimeraforge.monitor_connection import MonitorConnection

    async def operation(
        request: FleetMonitorRequest,
        config: api.FleetExporterConfig,
        connections: dict[str, MonitorConnection] | None,
    ) -> None:
        stop = asyncio.Event()
        signals = [signal.SIGINT, signal.SIGTERM]
        previous = {value: signal.getsignal(value) for value in signals}
        for value in signals:
            signal.signal(value, lambda *_: stop.set())
        try:
            async with api.serve_fleet_exporter(
                from_plan,
                request,
                config=config,
                candidate_index=candidate_index,
                connections=connections,
            ) as running:
                typer.echo(
                    json.dumps(
                        {
                            "kind": "chimeraforge.fleet-exporter-ready",
                            "metrics_url": running.metrics_url,
                            "replicas": len(request.endpoints),
                            "label_policy": "ordinal/configured-model",
                            "process_exit_is_qualification": False,
                        }
                    )
                )
                if run_seconds is None:
                    await stop.wait()
                else:
                    try:
                        await asyncio.wait_for(stop.wait(), run_seconds)
                    except asyncio.TimeoutError:
                        pass  # Optional operator-specified finite service duration.
            typer.echo(
                json.dumps(
                    {
                        "kind": "chimeraforge.fleet-exporter-closed",
                        "listener_joined": running.listener_joined,
                        "worker_joined": running.worker_joined,
                    }
                )
            )
        finally:
            for value, handler in previous.items():
                signal.signal(value, handler)

    try:
        if not 1 <= len(endpoint) <= MAX_ENDPOINTS:
            raise ValueError
        values = []
        for item in endpoint:
            if (
                type(item) is not str
                or len(item) > MAX_ID_CHARS + MAX_URL_CHARS + 1
                or "=" not in item
            ):
                raise ValueError
            name, url = item.split("=", 1)
            values.append(FleetEndpoint(name, url))
        if run_seconds is not None and (
            not math.isfinite(run_seconds) or not 0 < run_seconds <= 86400
        ):
            raise ValueError
        config = api.FleetExporterConfig(
            host=listen_host,
            port=listen_port,
            poll_seconds=poll_seconds,
            stale_after_seconds=stale_after_seconds,
            max_clients=max_clients,
        )
        config.validate()
        request = FleetMonitorRequest(
            tuple(values),
            interval=interval,
            windows=1,
            timeout=timeout,
            observation_seconds=observation_seconds,
            cleanup_seconds=cleanup_seconds,
            concurrency=concurrency,
            max_requests=max_requests,
            max_body_bytes=max_body_bytes,
            ttft_slo=ttft_slo,
            tpot_slo=tpot_slo,
        )
        connections = None
        if secure or any(v is not None for v in (bearer_env, ca_bundle, client_cert, client_key)):
            settings: dict[str, dict[str, str]] = {v.id: {} for v in values}
            for field, declarations in (
                ("bearer_env", bearer_env),
                ("ca_bundle", ca_bundle),
                ("client_cert", client_cert),
                ("client_key", client_key),
            ):
                if declarations is None:
                    continue
                if len(declarations) > MAX_ENDPOINTS:
                    raise ValueError
                for declaration in declarations:
                    if len(declaration) > MAX_URL_CHARS or "=" not in declaration:
                        raise ValueError
                    name, value = declaration.split("=", 1)
                    if name not in settings or not value or field in settings[name]:
                        raise ValueError
                    settings[name][field] = value
            connections = {
                v.id: MonitorConnection.from_env(v.url, **settings[v.id]) for v in values
            }
        asyncio.run(operation(request, config, connections))
    except (ValueError, OSError, RuntimeError):
        typer.echo("Error: invalid, unsupported or unavailable fleet exporter", err=True)
        raise typer.Exit(1) from None
