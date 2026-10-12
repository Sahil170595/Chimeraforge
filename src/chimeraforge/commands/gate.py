"""A predeclared conditional engineering regression gate over saved measurements."""

from __future__ import annotations

import json
from pathlib import Path

import typer


def gate(
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
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Exit 0 conditional pass, 1 regression, 2 malformed, 3 inconclusive."""
    from chimeraforge import api
    from chimeraforge.plan_study import protect_output

    try:
        if out is not None:
            protect_output(out, [*baseline, *candidate, policy])
        result = api.gate_benchmarks(baseline, candidate, policy=policy)
        if out is not None:
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
