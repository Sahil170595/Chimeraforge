"""Portable, integrity-checked saved-plan handoff."""

import json
from pathlib import Path

import typer

bundle_app = typer.Typer(
    help="Handoff bound plan inputs offline. Harness files may contain private data.",
    no_args_is_help=True,
)


def _emit(operation, *args, json_output: bool = False) -> None:
    from chimeraforge.api import PlanError

    try:
        report = operation(*args).to_dict()
    except PlanError as exc:
        if json_output:
            typer.echo(json.dumps({"error": str(exc)}))
        else:
            typer.echo(f"Invalid plan bundle: {exc}")
        raise typer.Exit(2) from exc
    if json_output:
        typer.echo(json.dumps(report, allow_nan=False))
    else:
        typer.echo(
            f"Plan bundle: {report.get('status', 'verified_content')} ({report.get('fingerprint')})"
        )
        typer.echo("Integrity does not authenticate inputs or prove served weights/performance.")
    raise typer.Exit(report.get("exit_code", 0))


@bundle_app.command()
def create(
    plan_path: Path = typer.Argument(..., help="Original saved plan JSON."),
    out: Path = typer.Option(..., "--out", help="New directory; parent must exist."),
    json_output: bool = typer.Option(
        False, "--json", help="Safe metadata only; no harness payloads."
    ),
) -> None:
    """Copy exact bound inputs. Harness files may contain private data: review before sharing."""
    from chimeraforge.api import create_plan_bundle

    _emit(create_plan_bundle, plan_path, out, json_output=json_output)


@bundle_app.command()
def verify(
    directory: Path = typer.Argument(..., help="Portable bundle directory."),
    json_output: bool = typer.Option(False, "--json", help="Emit membership/content verification."),
) -> None:
    """Verify original bytes, role membership and producing input semantics."""
    from chimeraforge.api import verify_plan_bundle

    _emit(verify_plan_bundle, directory, json_output=json_output)


@bundle_app.command()
def check(
    directory: Path = typer.Argument(..., help="Portable bundle directory."),
    json_output: bool = typer.Option(
        False, "--json", help="Emit offline replay and relocation evidence."
    ),
) -> None:
    """Recheck held inputs offline; exit 1 for changed/expired/required unverified facts."""
    from chimeraforge.api import check_plan_bundle

    _emit(check_plan_bundle, directory, json_output=json_output)
