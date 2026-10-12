"""Frozen-context workload and cost sensitivity study."""

import json
from pathlib import Path

import typer


def study(
    saved: Path = typer.Argument(..., help="Bound saved plan or verified bundle directory."),
    cases: Path = typer.Option(
        ..., "--cases", help="JSON list of unique name/changes objects, up to 16."
    ),
    out: Path | None = typer.Option(
        None, "--out", help="Optional study JSON; cannot replace input files."
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit native-unit modeled comparisons."),
) -> None:
    """Compare explicit scenarios offline; infeasible cases remain in the completed study."""
    from chimeraforge import api
    from chimeraforge.plan_study import load_cases, protect_output

    try:
        if out is not None:
            protect_output(out, [saved, cases])
        report = api.study_plan(saved, load_cases(cases))
        if out is not None:
            report.save(out)
        data = report.to_dict()
    except api.PlanError as exc:
        typer.echo(json.dumps({"error": str(exc)}) if json_output else f"Invalid study: {exc}")
        raise typer.Exit(2) from exc
    if json_output:
        typer.echo(json.dumps(data, allow_nan=False))
    else:
        for row in data["scenarios"]:
            typer.echo(
                f"{row['name']}: {'feasible' if row['feasible'] else 'infeasible'}; "
                f"configuration switch {row['configuration_switch']}"
            )
        typer.echo("Modeled sensitivity; served weights and performance remain unverified.")
