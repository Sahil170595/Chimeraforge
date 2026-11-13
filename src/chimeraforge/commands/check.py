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
    network: bool = typer.Option(
        False,
        "--network",
        help="Explicitly inspect bound HF metadata and current requested refs on the Hub.",
    ),
    hf_token: str = typer.Option(
        None, "--hf-token", help="HF token for this inspection only (else $HF_TOKEN); never saved."
    ),
    junit: Path | None = typer.Option(
        None, "--junit", help="Write a bounded JUnit report separately from stdout."
    ),
) -> None:
    """Recheck saved inputs and modeled recommendations; offline unless --network."""
    from chimeraforge.api import PlanError, check_plan

    try:
        if junit is not None:
            from chimeraforge.plan_check_output import (
                plan_input_paths,
                protect_junit,
                publish_junit,
            )

            protect_junit(junit, (plan_path,))
        report = check_plan(plan_path, allow_network=network, hf_token=hf_token).to_dict()
        if junit is not None:
            publish_junit(report, junit, (plan_path, *plan_input_paths(report)))
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
        for model, fields in report["checkpoint_view"].items():
            for name, component in fields.items():
                console.print(f"{model} {name}: {component['state']}", markup=False)
        console.print(report["performance"]["detail"], markup=False)
    raise typer.Exit(report["exit_code"])
