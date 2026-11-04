"""Observe explicit latency SLOs without creating traffic or detached processes."""

from __future__ import annotations

import json
from pathlib import Path

import typer


def monitor(
    backend: str = typer.Option(..., "--backend", help="Metrics contract: vllm or sglang."),
    url: str = typer.Option(..., "--url", help="HTTP(S) /metrics endpoint or server base URL."),
    model: str = typer.Option(..., "--model", help="Exact model_name label; never pool models."),
    ttft_slo: float | None = typer.Option(None, "--ttft-slo", help="Observed P95 TTFT target, ms."),
    tpot_slo: float | None = typer.Option(None, "--tpot-slo", help="Request TPOT P95 target, ms."),
    interval: float = typer.Option(30.0, "--interval", help="Seconds between metrics scrapes."),
    windows: int = typer.Option(1, "--windows", help="Finite number of observation windows."),
    timeout: float = typer.Option(10.0, "--timeout", help="Metrics request timeout, seconds."),
    from_plan: Path | None = typer.Option(
        None,
        "--from-plan",
        help="Bind a saved candidate and its targets to observed serving metadata.",
    ),
    candidate_index: int = typer.Option(
        0, "--candidate-index", help="Saved candidate index (requires --from-plan)."
    ),
    output_json: bool = typer.Option(False, "--json", help="Print one aggregate JSON report."),
    prometheus: Path | None = typer.Option(
        None, "--prometheus", help="Atomic textfile gauge output."
    ),
    secure: bool = typer.Option(
        False, "--secure", help="Require verified HTTPS with explicit trust."
    ),
    bearer_env: str | None = typer.Option(
        None, "--bearer-env", help="Read bearer once from this named environment variable."
    ),
    ca_bundle: Path | None = typer.Option(
        None, "--ca-bundle", help="Private PEM CA bundle replacing default roots."
    ),
    client_cert: Path | None = typer.Option(
        None, "--client-cert", help="Client certificate PEM (requires key)."
    ),
    client_key: Path | None = typer.Option(
        None, "--client-key", help="Unencrypted client key PEM (requires certificate)."
    ),
) -> None:
    """Monitor bounded two-scrape SLO windows (pass 0, breach 3, unknown 4)."""
    from chimeraforge.api import PlanError, monitor_plan
    from chimeraforge.monitor import MonitorError, MonitorRequest, run_monitor, write_prometheus
    from chimeraforge.monitor_connection import MonitorConnection, MonitorConnectionError
    from chimeraforge.plan_study import protect_output

    try:
        if from_plan is None and candidate_index != 0:
            raise MonitorError("--candidate-index requires --from-plan")
        if prometheus is not None:
            try:
                protect_output(
                    prometheus,
                    tuple(
                        value
                        for value in (from_plan, ca_bundle, client_cert, client_key)
                        if value is not None
                    ),
                )
            except (PlanError, OSError, RuntimeError):
                raise MonitorError(
                    "--prometheus must not overwrite monitoring inputs; invalid output destination"
                ) from None
        request = MonitorRequest(
            backend, url, model, ttft_slo, tpot_slo, interval, windows, timeout
        )
        connection = (
            MonitorConnection.from_env(
                url,
                bearer_env=bearer_env,
                ca_bundle=ca_bundle,
                client_cert=client_cert,
                client_key=client_key,
            )
            if secure
            or any(value is not None for value in (bearer_env, ca_bundle, client_cert, client_key))
            else None
        )
        report = (
            monitor_plan(from_plan, request, candidate_index=candidate_index, connection=connection)
            if from_plan is not None
            else run_monitor(request, connection=connection)
        )
        if prometheus is not None:
            write_prometheus(report, prometheus)
    except (MonitorError, PlanError, MonitorConnectionError) as exc:
        if output_json:
            typer.echo(json.dumps({"error": str(exc)}, allow_nan=False))
        else:
            typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    if output_json:
        typer.echo(json.dumps(report.to_dict(), indent=2, allow_nan=False))
    else:
        typer.echo(
            f"{report.backend} {report.model}: {report.outcome} "
            f"({len(report.windows)} completed windows)"
        )
        for result in report.windows:
            for name, metric in result.metrics.items():
                if metric.target_ms is None:
                    continue
                bound = "unknown" if metric.p95_upper_ms is None else f"{metric.p95_upper_ms:g} ms"
                typer.echo(f"  {name}: {metric.outcome}; P95 upper bound {bound}; {metric.reason}")
        if report.cancelled:
            typer.echo("  cancelled: incomplete observation cannot establish a pass")
        if report.plan_binding is not None:
            typer.echo(
                f"  plan identity: {report.plan_binding['identity']['state']}; "
                f"configuration: {report.plan_binding['configuration']['state']}"
            )
    raise typer.Exit(report.exit_code)
