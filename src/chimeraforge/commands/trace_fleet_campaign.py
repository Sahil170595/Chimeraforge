"""Run serial whole-original-fleet executions over one held native preparation."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
import signal

import typer

from chimeraforge.fleet_monitor_types import MAX_ENDPOINTS, MAX_ID_CHARS, MAX_URL_CHARS


LOG = logging.getLogger(__name__)


def trace_fleet_campaign(
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
    executions: int = typer.Option(3, "--executions"),
    campaign_timeout: float = typer.Option(1800, "--campaign-timeout"),
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
    """K serial original fleets: native qualification0/1, malformed or export-profile error2."""
    from chimeraforge import api
    from chimeraforge.bench.fleet_campaign import (
        _replay_campaign_prepared,
        prepare_campaign,
        _clock,
    )
    from chimeraforge.bench.fleet_campaign_types import FleetTraceCampaignError
    from chimeraforge.bench.fleet_gate_output import _write
    from chimeraforge.monitor_connection import MonitorConnection, MonitorConnectionError
    from chimeraforge.plan_study import protect_output

    async def execute() -> api.FleetTraceCampaign:
        origin = _clock()
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
                        from_plan,
                        workload,
                        routes,
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
            held = prepare_campaign(
                from_plan,
                workload,
                tuple(values),
                routes,
                executions=executions,
                candidate_index=candidate_index,
                model=model,
                concurrency=concurrency,
                request_timeout=request_timeout,
                trace_timeout=trace_timeout,
                cleanup_timeout=cleanup_timeout,
                campaign_timeout=campaign_timeout,
                stop_event=stopped,
                connections=connections,
                _origin=origin,
            )
            if out is not None:
                protect_output(out, held[2])
            return await _replay_campaign_prepared(held, stopped)
        finally:
            signal.signal(signal.SIGINT, previous)

    receipt = None
    try:
        receipt = asyncio.run(execute())
        raw = receipt.json_bytes() if json_output or out is not None else None
        if out is not None:
            protect_output(out, receipt._input_paths)
            assert raw is not None
            _write(out, raw)
    except (
        api.PlanError,
        MonitorConnectionError,
        FleetTraceCampaignError,
        OSError,
        ValueError,
        TypeError,
        RuntimeError,
    ) as exc:
        LOG.info("fleet campaign CLI refused (%s)", type(exc).__name__)
        message = "invalid, unavailable or over-limit whole-fleet campaign"
        diagnostic: dict[str, object] = {"error": message}
        if receipt is not None:
            diagnostic["native_exit_code"] = receipt.exit_code
        typer.echo(json.dumps(diagnostic) if json_output else message)
        raise typer.Exit(2) from None
    if json_output:
        assert raw is not None
        typer.echo(raw, nl=False)
    else:
        data = receipt._data
        counts = data["execution"]
        typer.echo(
            f"Completed {counts['completed']}/{counts['planned']} whole-fleet executions; "
            f"original_members={data['manifest']['population']['original_replicas']}"
        )
        states = ",".join(
            str(slot["index"])
            + ":"
            + (slot["receipt"]["slo"]["state"] if slot["receipt"] is not None else "unavailable")
            for slot in data["executions"]
        )
        typer.echo(
            f"execution={data['state']} configuration={data['configuration_status']} "
            f"slo={states} cleanup={data['cleanup']['state']} exit={data['exit_code']}"
        )
        typer.echo(data["limits"])
    raise typer.Exit(receipt.exit_code)
