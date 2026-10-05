"""CLI for config-only deployment export from a validated saved plan."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console


def deploy(
    plan_path: Path = typer.Option(..., "--plan", help="Saved plan JSON from plan --save."),
    format: str = typer.Option(..., "--format", help="compose, systemd, launchd or modelfile."),
    out: Path = typer.Option(
        ..., "--out", help="New output file; companion files use its directory."
    ),
    model: str | None = typer.Option(
        None, "--model", help="Concrete identity for an unresolved size-class plan."
    ),
    image: str | None = typer.Option(
        None, "--image", help="Explicit non-latest container tag or digest for Compose."
    ),
    candidate_index: int = typer.Option(
        0, "--candidate-index", help="Zero-based saved candidate index."
    ),
    executable: str | None = typer.Option(
        None, "--executable", help="Absolute installed engine/interpreter path for native units."
    ),
) -> None:
    """Write serving config; no engines are installed, started or deployed."""
    from chimeraforge.api import PlanError, load_plan
    from chimeraforge.deploy import DeploymentError, export_deployment

    console = Console()
    try:
        result = export_deployment(
            load_plan(plan_path),
            format=format,
            model=model,
            image=image,
            candidate_index=candidate_index,
            executable=executable,
        )
        outputs = {
            out: result.content,
            **{out.parent / name: text for name, text in result.files.items()},
        }
        if len(outputs) != 1 + len(result.files):
            raise DeploymentError("output name collides with a required companion file")
        for path in outputs:
            if path.exists():
                raise DeploymentError(
                    f"output already exists: {path}; choose a new output directory/file"
                )
        for path, content in outputs.items():
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
    except (PlanError, DeploymentError, OSError) as exc:
        console.print(f"Deployment export failed: {exc}", markup=False)
        raise typer.Exit(1) from exc
    console.print(f"Config only: wrote {out}", markup=False)
    for note in result.notes:
        console.print(f"Note: {note}", markup=False)
    for instruction in result.provisioning:
        console.print(instruction, markup=False)
