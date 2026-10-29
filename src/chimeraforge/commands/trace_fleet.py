"""Replay one saved original fleet with an explicit held direct route map."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import signal

import typer

from chimeraforge.fleet_monitor_types import MAX_ENDPOINTS, MAX_ID_CHARS, MAX_URL_CHARS


def trace_fleet(
    workload: Path = typer.Argument(
        ..., help="Private native request JSON; prompts reach endpoints."
    ),
    from_plan: Path = typer.Option(..., "--from-plan"),
    endpoint: list[str] = typer.Option(
        ..., "--endpoint", help="Repeat ID=URL for every original member."
    ),
    routes: Path = typer.Option(
        ..., "--routes", help="Closed request_id/endpoint_id JSON route list."
    ),
    candidate_index: int = typer.Option(0, "--candidate-index"),
    model: str | None = typer.Option(
        None, "--model", help="Explicit served alias; original plan held."
    ),
    concurrency: int = typer.Option(1, "--concurrency"),
    request_timeout: float = typer.Option(300, "--request-timeout"),
    trace_timeout: float = typer.Option(600, "--trace-timeout"),
    cleanup_timeout: float = typer.Option(2, "--cleanup-timeout"),
    out: Path | None = typer.Option(None, "--out"),
    json_output: bool = typer.Option(False, "--json"),
    secure: bool = typer.Option(False, "--secure", help="Verified HTTPS for all declared members."),
    bearer_env: list[str] | None = typer.Option(None, "--bearer-env", help="Repeat ID=ENV_NAME."),
    ca_bundle: list[str] | None = typer.Option(None, "--ca-bundle", help="Repeat ID=PEM_PATH."),
    client_cert: list[str] | None = typer.Option(None, "--client-cert", help="Repeat ID=PEM_PATH."),
    client_key: list[str] | None = typer.Option(None, "--client-key", help="Repeat ID=PEM_PATH."),
) -> None:
    """One global replay: complete0, incomplete/mismatch1, invalid2; SLO is separate."""
    from chimeraforge import api
    from chimeraforge.bench.fleet_trace import _replay_prepared
    from chimeraforge.bench.fleet_trace_inputs import prepare
    from chimeraforge.monitor_connection import MonitorConnection, MonitorConnectionError
    from chimeraforge.plan_study import protect_output

    async def execute() -> api.FleetTraceReplay:
        stopped = asyncio.Event()
        previous = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, lambda *_: stopped.set())
        try:
            if len(endpoint) > MAX_ENDPOINTS:
                raise api.PlanError("invalid endpoint count")
            values = []
            for declaration in endpoint:
                if len(declaration) > MAX_ID_CHARS + 1 + MAX_URL_CHARS or "=" not in declaration:
                    raise api.PlanError("invalid endpoint declaration")
                name, url = declaration.split("=", 1)
                values.append(api.FleetEndpoint(name, url))
            prepared = prepare(
                from_plan,
                workload,
                tuple(values),
                routes,
                candidate_index=candidate_index,
                model=model,
                concurrency=concurrency,
                request_timeout=request_timeout,
                trace_timeout=trace_timeout,
                cleanup_timeout=cleanup_timeout,
                stop_event=stopped,
            )
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
                    raise api.PlanError("invalid secure settings")
                for declaration in declarations:
                    if len(declaration) > MAX_URL_CHARS or "=" not in declaration:
                        raise api.PlanError("invalid secure settings")
                    name, setting = declaration.split("=", 1)
                    if name not in settings or not setting or field in settings[name]:
                        raise api.PlanError("invalid secure settings")
                    settings[name][field] = setting
            if out is not None:
                protect_output(
                    out,
                    (
                        *prepared.protected_paths,
                        *(
                            Path(setting)
                            for configuration in settings.values()
                            for field, setting in configuration.items()
                            if field != "bearer_env"
                        ),
                    ),
                )
            connections = None
            if secure or any(
                value is not None for value in (bearer_env, ca_bundle, client_cert, client_key)
            ):
                connections = {
                    value.id: MonitorConnection.from_env(value.url, **settings[value.id])
                    for value in values
                }
            return await _replay_prepared(prepared, connections)
        finally:
            signal.signal(signal.SIGINT, previous)

    try:
        receipt = asyncio.run(execute())
        if out is not None:
            receipt.save(out)
        report = receipt.to_dict()
    except (api.PlanError, MonitorConnectionError, OSError, ValueError, TypeError, RuntimeError):
        message = "invalid or unavailable original-fleet trace"
        typer.echo(json.dumps({"error": message}) if json_output else message)
        raise typer.Exit(2) from None
    if json_output:
        typer.echo(json.dumps(report, allow_nan=False))
    else:
        native = report["native_trace"]
        typer.echo(
            f"Completed {native['execution']['completed']}/{native['execution']['planned']} "
            f"requests across {len(report['slots'])} declared members"
        )
        typer.echo(
            f"execution={report['status']} configuration={report['configuration_status']} "
            f"slo={report['slo']['state']} cleanup={report['cleanup']['state']} "
            f"exit={report['exit_code']}"
        )
        typer.echo(report["limits"])
    raise typer.Exit(report["exit_code"])
