"""Observe every explicitly declared saved replica without generating traffic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import signal

import typer

from chimeraforge.fleet_monitor_types import FleetMonitorExportError, FleetMonitorReport


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
    out: Path | None = typer.Option(None, "--out", help="Bounded complete JSON receipt."),
    prometheus: Path | None = typer.Option(None, "--prometheus"),
    secure: bool = typer.Option(
        False, "--secure", help="Verified HTTPS for every declared endpoint."
    ),
    bearer_env: list[str] | None = typer.Option(
        None, "--bearer-env", help="Repeat ID=ENV_NAME; no credential broadcast."
    ),
    ca_bundle: list[str] | None = typer.Option(
        None, "--ca-bundle", help="Repeat ID=PEM_PATH; replaces that endpoint roots."
    ),
    client_cert: list[str] | None = typer.Option(
        None, "--client-cert", help="Repeat ID=PEM_PATH (requires key)."
    ),
    client_key: list[str] | None = typer.Option(
        None, "--client-key", help="Repeat ID=PEM_PATH (requires certificate)."
    ),
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
    from chimeraforge.monitor_connection import MonitorConnection

    async def operation(request: FleetMonitorRequest) -> FleetMonitorReport:
        stop = asyncio.Event()
        previous = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, lambda *_: stop.set())
        try:
            return await observe(
                from_plan,
                request,
                candidate_index=candidate_index,
                stop_event=stop,
                connections=connections,
            )
        finally:
            signal.signal(signal.SIGINT, previous)

    report = None
    try:
        if len(endpoint) > MAX_ENDPOINTS:
            raise FleetMonitorError("at most 16 endpoint declarations are admitted")
        values = []
        for declaration in endpoint:
            if len(declaration) > MAX_ID_CHARS + 1 + MAX_URL_CHARS or "=" not in declaration:
                raise FleetMonitorError("endpoint must be bounded ID=URL")
            name, url = declaration.split("=", 1)
            values.append(FleetEndpoint(name, url))
        outputs = [path for path in (out, prometheus) if path is not None]
        for position, path in enumerate(outputs):
            protect_output(path, (from_plan, *outputs[:position], *outputs[position + 1 :]))
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
        connections = None
        if secure or any(
            value is not None for value in (bearer_env, ca_bundle, client_cert, client_key)
        ):
            settings: dict[str, dict[str, str]] = {value.id: {} for value in values}
            for field, declarations in (
                ("bearer_env", bearer_env),
                ("ca_bundle", ca_bundle),
                ("client_cert", client_cert),
                ("client_key", client_key),
            ):
                if declarations is None:
                    continue
                if len(declarations) > MAX_ENDPOINTS:
                    raise FleetMonitorError("invalid fleet secure configuration")
                for declaration in declarations:
                    if len(declaration) > MAX_URL_CHARS or "=" not in declaration:
                        raise FleetMonitorError("invalid fleet secure configuration")
                    name, setting = declaration.split("=", 1)
                    if name not in settings or not setting or field in settings[name]:
                        raise FleetMonitorError("invalid fleet secure configuration")
                    settings[name][field] = setting
            for path in outputs:
                protect_output(
                    path,
                    tuple(
                        Path(setting)
                        for configuration in settings.values()
                        for field, setting in configuration.items()
                        if field != "bearer_env"
                    ),
                )
            connections = {
                value.id: MonitorConnection.from_env(value.url, **settings[value.id])
                for value in values
            }
            for path in outputs:
                protect_output(
                    path,
                    tuple(
                        p for connection in connections.values() for p in connection._input_paths()
                    ),
                )
        report = asyncio.run(operation(request))
        raw = report.json_bytes() if output_json or out is not None else None
        # Admit every requested JSON projection before either per-file publication.
        for path in outputs:
            protect_output(path, report._protected_paths)
        if out is not None:
            from chimeraforge.bench.fleet_gate_output import _write

            assert raw is not None
            _write(out, raw)
        if prometheus is not None:
            write_prometheus(report, prometheus)
    except FleetMonitorExportError:
        native_code = report.exit_code if report is not None else 4
        code = native_code if native_code in (3, 5) else 4
        diagnostic = {
            "kind": "chimeraforge.fleet-monitor-export-error",
            "error": "complete fleet JSON exceeds the 8 MiB export limit",
            "producer_declared_native_exit_code": native_code,
            "exit_code": code,
        }
        typer.echo(json.dumps(diagnostic) if output_json else diagnostic["error"])
        raise typer.Exit(code) from None
    except (FleetMonitorError, PlanError, OSError, ValueError, RuntimeError):
        if output_json:
            typer.echo(
                json.dumps({"error": "invalid, unsupported or unavailable fleet observation"})
            )
        else:
            typer.echo("Error: invalid, unsupported or unavailable fleet observation", err=True)
        raise typer.Exit(1) from None
    if output_json:
        assert raw is not None
        typer.echo(raw, nl=False)
    else:
        outcome = {0: "pass", 3: "breach", 4: "unknown", 5: "mismatch"}[report.exit_code]
        typer.echo(
            f"Declared fleet: {outcome}; "
            f"{sum(slot.state == 'complete' for slot in report.slots)}/{len(report.slots)} complete"
        )
        for slot in report.slots:
            typer.echo(
                f"  {slot.id}: {slot.state}; SLO {slot.slo}; "
                f"identity {slot.binding['identity']['state']}"
            )
    raise typer.Exit(report.exit_code)
