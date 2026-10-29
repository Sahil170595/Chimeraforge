"""A predeclared conditional engineering regression gate over saved measurements."""

from __future__ import annotations

import json
from pathlib import Path

import typer


def gate(
    kind: str = typer.Option(
        "benchmark", "--kind", help="Receipt kind: benchmark, trace, trace-campaign or fleet-trace."
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
    out: Path | None = typer.Option(
        None, "--out", help="Atomic decision receipt; cannot replace inputs."
    ),
    junit: Path | None = typer.Option(
        None, "--junit", help="Fleet-trace JUnit; cannot replace inputs or decision."
    ),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Exit 0 conditional pass, 1 regression, 2 malformed, 3 inconclusive."""
    from chimeraforge import api
    from chimeraforge.plan_study import protect_output

    try:
        if kind not in ("benchmark", "trace", "trace-campaign", "fleet-trace"):
            raise api.PlanError(
                "gate --kind must be benchmark, trace, trace-campaign or fleet-trace"
            )
        if kind in ("trace-campaign", "fleet-trace") and (
            len(baseline) != 1 or len(candidate) != 1
        ):
            raise api.PlanError("whole-population gate needs exactly one receipt per arm")
        if junit is not None and kind != "fleet-trace":
            raise api.PlanError("--junit requires --kind fleet-trace")
        if out is not None:
            protect_output(out, [*baseline, *candidate, policy])
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
        typer.echo(json.dumps({"error": str(exc)}) if json_output else str(exc))
        raise typer.Exit(2) from exc
    typer.echo(
        json.dumps(report, allow_nan=False)
        if json_output
        else report["outcome"] + ": " + report["limits"]
    )
    raise typer.Exit(report["exit_code"])
