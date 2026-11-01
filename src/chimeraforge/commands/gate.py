"""A predeclared conditional engineering regression gate over saved measurements."""

from __future__ import annotations

import json
from pathlib import Path

import typer


def gate(
    kind: str = typer.Option(
        "benchmark",
        "--kind",
        help=(
            "benchmark, trace, trace-campaign, fleet-trace, fleet-monitor or fleet-trace-campaign."
        ),
    ),
    baseline: list[Path] = typer.Option(
        ..., "--baseline", help="Ordered baseline receipt; repeat for every replicate."
    ),
    candidate: list[Path] = typer.Option(
        ..., "--candidate", help="Ordered candidate receipt; repeat for every replicate."
    ),
    policy: Path = typer.Option(
        ..., "--policy", help="Explicit JSON rules, population and observed conditions."
    ),
    baseline_plan: Path | None = typer.Option(
        None, "--baseline-plan", help="Original baseline monitor plan."
    ),
    candidate_plan: Path | None = typer.Option(
        None, "--candidate-plan", help="Original candidate monitor plan."
    ),
    out: Path | None = typer.Option(
        None, "--out", help="Atomic decision receipt; cannot replace inputs."
    ),
    junit: Path | None = typer.Option(
        None, "--junit", help="Whole-fleet JUnit; cannot replace inputs or decision."
    ),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Exit 0 conditional pass, 1 regression, 2 malformed, 3 inconclusive."""
    from chimeraforge import api
    from chimeraforge.plan_study import protect_output

    try:
        if kind not in (
            "benchmark",
            "trace",
            "trace-campaign",
            "fleet-trace",
            "fleet-monitor",
            "fleet-trace-campaign",
        ):
            raise api.PlanError(
                "gate --kind must be benchmark, trace, trace-campaign, fleet-trace, "
                "fleet-monitor or fleet-trace-campaign"
            )
        if kind in ("trace-campaign", "fleet-trace", "fleet-monitor", "fleet-trace-campaign") and (
            len(baseline) != 1 or len(candidate) != 1
        ):
            raise api.PlanError("whole-population gate needs exactly one receipt per arm")
        if junit is not None and kind not in (
            "fleet-trace",
            "fleet-monitor",
            "fleet-trace-campaign",
        ):
            raise api.PlanError("--junit requires a whole-fleet gate")
        if kind != "fleet-monitor" and (baseline_plan is not None or candidate_plan is not None):
            raise api.PlanError("original monitor plans require --kind fleet-monitor")
        if out is not None:
            protect_output(out, [*baseline, *candidate, policy])
        if kind == "fleet-trace-campaign":
            from chimeraforge.bench.fleet_campaign_output import publish as publish_campaign

            campaign_result = api.gate_fleet_trace_campaigns(
                baseline[0], candidate[0], policy=policy
            )
            campaign_raw = publish_campaign(campaign_result, out=out, junit=junit)
            campaign_report = json.loads(campaign_raw)
            typer.echo(
                campaign_raw
                if json_output
                else campaign_report["outcome"] + ": " + campaign_report["limits"],
                nl=not json_output,
            )
            raise typer.Exit(campaign_report["exit_code"])
        if kind == "fleet-monitor":
            if baseline_plan is None or candidate_plan is None:
                raise api.PlanError("fleet-monitor requires both original source plans")
            monitor_result = api.gate_fleet_monitors(
                baseline[0],
                candidate[0],
                baseline_plan=baseline_plan,
                candidate_plan=candidate_plan,
                policy=policy,
            )
            from chimeraforge.fleet_monitor_gate_output import publish

            monitor_raw = publish(monitor_result, out=out, junit=junit)
            report = json.loads(monitor_raw)
            typer.echo(
                monitor_raw if json_output else report["outcome"] + ": " + report["limits"],
                nl=not json_output,
            )
            raise typer.Exit(report["exit_code"])
        if kind == "fleet-trace":
            result = api.gate_fleet_traces(baseline[0], candidate[0], policy=policy)
        elif kind == "trace-campaign":
            result = api.gate_trace_campaigns(baseline[0], candidate[0], policy=policy)
        elif kind == "trace":
            result = api.gate_traces(list(baseline), list(candidate), policy=policy)
        else:
            result = api.gate_benchmarks(list(baseline), list(candidate), policy=policy)
        if kind == "fleet-trace" and (out is not None or junit is not None):
            api.write_fleet_trace_gate(result, out=out, junit=junit)
        elif out is not None:
            result.save(out)
        report = result.to_dict()
    except api.PlanError as exc:
        if kind == "fleet-trace-campaign":
            message = "invalid or unavailable complete fleet campaign decision"
            typer.echo(json.dumps({"error": message}) if json_output else message)
            raise typer.Exit(2) from None
        typer.echo(json.dumps({"error": str(exc)}) if json_output else str(exc))
        raise typer.Exit(2) from exc
    typer.echo(
        json.dumps(report, allow_nan=False)
        if json_output
        else report["outcome"] + ": " + report["limits"]
    )
    raise typer.Exit(report["exit_code"])
