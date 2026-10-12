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
) -> None:
    """Recheck saved inputs and modeled recommendations; offline unless --network."""
    from chimeraforge.api import PlanError, check_plan

    try:
        report = check_plan(plan_path, allow_network=network, hf_token=hf_token).to_dict()
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
