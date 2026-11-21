"""Frozen-context workload, hardware and cost sensitivity study."""

import json
from pathlib import Path

import typer


def study(
    saved: Path = typer.Argument(..., help="Bound saved plan or verified bundle directory."),
    cases: Path = typer.Option(
        ..., "--cases", help="Up to 16 name/changes objects; hardware requires an exact GPU name."
    ),
    out: Path | None = typer.Option(
        None, "--out", help="Optional study JSON; cannot replace input files."
    ),
    require_all_feasible: bool = typer.Option(
        False,
        "--require-all-feasible",
        help="Require native feasible candidates for the base and every original scenario.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit native-unit modeled comparisons."),
) -> None:
    """Compare explicit scenarios offline; infeasible cases remain in the completed study."""
    from chimeraforge import api
    from chimeraforge.plan_study import load_cases, protect_output

    try:
        if out is not None:
            protect_output(out, [saved, cases])
        report = api.study_plan(
            saved,
            load_cases(cases),
            feasibility_policy=api.StudyFeasibilityPolicy() if require_all_feasible else None,
        )
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
        if "feasibility_requirement" in data:
            requirement = data["feasibility_requirement"]
            state = "met" if requirement["met"] else "unmet"
            typer.echo(
                f"All-feasible requirement {state}: "
                f"{requirement['feasible_rows']}/{requirement['expected_rows']} original rows."
            )
        typer.echo("Modeled sensitivity; served weights and performance remain unverified.")
    if data["exit_code"] != 0:
        raise typer.Exit(data["exit_code"])
