"""Assess declared finite load points from complete saved campaigns offline."""

from __future__ import annotations

import json
from pathlib import Path

import typer


def trace_envelope(
    cases: Path = typer.Option(..., "--cases", help="Frozen uniform schedules and population."),
    policy: Path = typer.Option(..., "--policy", help="Explicit targets and observed conditions."),
    fleet: bool = typer.Option(False, "--fleet", help="Assess native whole-fleet campaigns."),
    plan: Path | None = typer.Option(None, "--plan", help="Original plan required with --fleet."),
    candidate_index: int | None = typer.Option(
        None, "--candidate-index", help="Original fleet candidate index."
    ),
    campaign: list[str] = typer.Option(
        [],
        "--campaign",
        help="CELL=PATH; CELL excludes '='; PATH may contain '='. Repeat per cell.",
    ),
    out: Path | None = typer.Option(None, "--out", help="Atomic assessment; protects all inputs."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Exit 0 conditional pass, 1 SLO breach, 2 invalid, 3 incomplete/incompatible."""
    from chimeraforge import api
    from chimeraforge.plan_study import protect_output

    try:
        if (
            fleet
            and (plan is None or candidate_index is None)
            or not fleet
            and (plan is not None or candidate_index is not None)
        ):
            raise api.PlanError(
                "fleet mode requires its original plan and independent candidate selection"
            )
        supplied: dict[str, Path] = {}
        for assignment in campaign:
            name, separator, filename = assignment.partition("=")
            if not separator or not name.strip() or not filename.strip():
                raise api.PlanError("--campaign requires a nonempty CELL=PATH assignment")
            if name in supplied:
                raise api.PlanError("--campaign cannot repeat a cell name")
            supplied[name] = Path(filename)
        if out is not None:
            protect_output(
                out, [cases, policy, *supplied.values(), *([plan] if plan is not None else [])]
            )
        if fleet:
            assert plan is not None
            result = api.assess_fleet_trace_envelope(
                plan,
                cases,
                supplied,
                policy=policy,
                candidate_index=0 if candidate_index is None else candidate_index,
            )
        else:
            result = api.assess_trace_envelope(cases, supplied, policy=policy)
        if out is not None:
            result.save(out)
        report = result.to_dict()
    except api.PlanError as exc:
        typer.echo(json.dumps({"error": str(exc)}) if json_output else str(exc))
        raise typer.Exit(2) from exc
    if json_output:
        typer.echo(json.dumps(report, allow_nan=False))
    else:
        typer.echo(report["outcome"] + ": " + report["limits"])
        point = report.get("highest_observed_passing")
        if point is not None:
            typer.echo(
                f"Highest observed passing cell: {point.get('cell', point.get('cell_index'))} "
                f"({point['nominal_rate_rps']} req/s)"
            )
    raise typer.Exit(report["exit_code"])
