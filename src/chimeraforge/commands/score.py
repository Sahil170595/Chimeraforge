"""Explicit frozen prediction scorecards from saved native benchmark receipts."""

from __future__ import annotations

import json
from pathlib import Path

import typer


def score(
    plan: Path = typer.Option(
        ..., "--plan", help="Frozen saved plan or verified bundle directory."
    ),
    policy: Path = typer.Option(
        ..., "--policy", help="Required frozen plan/population/error-band policy."
    ),
    benchmark: list[Path] = typer.Option(
        [], "--benchmark", help="Native receipt; repeat for every observation."
    ),
    out: Path | None = typer.Option(
        None, "--out", help="Atomic scorecard; cannot replace consumed inputs."
    ),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Exit 0 within band, 1 known breach, 2 malformed/output failure, 3 incomplete."""
    from chimeraforge import api
    from chimeraforge.plan_study import protect_output

    try:
        if out is not None:
            protect_output(out, [plan, policy, *benchmark])
        result = api.score_predictions(plan, benchmark, policy=policy)
        if out is not None:
            result.save(out)
        report = result.to_dict()
    except (api.PlanError, OSError, ValueError, TypeError):
        message = "invalid prediction score input or output"
        typer.echo(json.dumps({"error": message}) if json_output else message)
        raise typer.Exit(2) from None
    typer.echo(
        json.dumps(report, allow_nan=False)
        if json_output
        else report["outcome"] + ": " + report["limits"]
    )
    raise typer.Exit(report["exit_code"])
