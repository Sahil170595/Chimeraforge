"""Portable, integrity-checked saved-plan handoff."""

from collections.abc import Callable
import json
from pathlib import Path
from typing import Any

import typer

bundle_app = typer.Typer(
    help="Handoff private plans and prediction evidence offline; review originals before sharing.",
    no_args_is_help=True,
)


def _emit(operation: Callable[..., Any], *args: Any, json_output: bool = False) -> None:
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


def _prediction_emit(
    operation: Callable[[], Any], *, json_output: bool, out: Path | None = None
) -> None:
    from chimeraforge.api import PlanError

    try:
        result = operation()
        if out is not None:
            result.save(out)
        report = result.to_dict()
    except PlanError as exc:
        typer.echo(json.dumps({"error": str(exc)}) if json_output else str(exc))
        raise typer.Exit(2) from exc
    if json_output:
        typer.echo(json.dumps(report, allow_nan=False))
    elif report["kind"] == "chimeraforge.prediction-scorecard":
        typer.echo(f"Prediction score: {report['outcome']}")
        typer.echo(report["limits"])
    else:
        typer.echo(f"Prediction evidence bundle: {report['status']} ({report['plan_fingerprint']})")
        typer.echo("Private handoff: original files may contain prompts, options and harness data.")
        typer.echo(report["limits"])
    raise typer.Exit(report.get("exit_code", 0))


@bundle_app.command("prediction-create")
def prediction_create(
    saved_plan: Path = typer.Argument(..., help="Original saved plan or verified plan bundle."),
    policy: Path = typer.Option(..., "--policy", help="Explicit prediction score policy."),
    benchmark: list[Path] = typer.Option(
        [], "--benchmark", help="Original receipt path, repeated in declared order. Zero is valid."
    ),
    out: Path = typer.Option(..., "--out", help="New private directory; parent must exist."),
    json_output: bool = typer.Option(False, "--json", help="Safe digest metadata only."),
) -> None:
    """Preserve private original bytes. Review every file before sharing."""
    from chimeraforge import api

    _prediction_emit(
        lambda: api.create_prediction_bundle(saved_plan, benchmark, policy=policy, outdir=out),
        json_output=json_output,
    )


@bundle_app.command("prediction-verify")
def prediction_verify(
    directory: Path = typer.Argument(..., help="Private prediction evidence bundle."),
    json_output: bool = typer.Option(False, "--json", help="Safe integrity metadata only."),
) -> None:
    """Verify closed inventory and held original bytes offline."""
    from chimeraforge import api

    _prediction_emit(lambda: api.verify_prediction_bundle(directory), json_output=json_output)


@bundle_app.command("prediction-score")
def prediction_score(
    directory: Path = typer.Argument(..., help="Private prediction evidence bundle."),
    out: Path | None = typer.Option(None, "--out", help="Scorecard; protects every bundle input."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Score held originals; exit 0 within band, 1 breach, 2 invalid, 3 incomplete."""
    from chimeraforge import api
    from chimeraforge.plan_study import protect_output

    def operation() -> Any:
        if out is not None:
            protect_output(out, [directory])
        return api.score_prediction_bundle(directory)

    _prediction_emit(operation, json_output=json_output, out=out)
