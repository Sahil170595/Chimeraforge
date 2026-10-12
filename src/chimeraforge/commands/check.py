"""CLI for offline comparison of an integrity-checked saved plan."""

from pathlib import Path
import json

import typer
from rich.console import Console


def check(
    plan_path: Path = typer.Argument(..., help="Saved plan JSON from plan --save."),
    json_output: bool = typer.Option(
        False, "--json", help="Emit comparison and evidence limits as JSON."
    ),
) -> None:
    """Recheck saved inputs, feasibility, pricing and modeled recommendations offline."""
    from chimeraforge.api import PlanError, check_plan

    try:
        report = check_plan(plan_path).to_dict()
    except PlanError as exc:
        if json_output:
            typer.echo(json.dumps({"error": str(exc)}))
        else:
            Console().print(f"Invalid saved plan: {exc}", markup=False)
        raise typer.Exit(2) from exc
    if json_output:
        typer.echo(json.dumps(report, allow_nan=False))
    else:
        console = Console()
        console.print(f"Plan check: {report['status']}", markup=False)
        for name, component in report["components"].items():
            console.print(f"{name}: {component['state']}", markup=False)
        console.print(report["performance"]["detail"], markup=False)
    raise typer.Exit(report["exit_code"])
