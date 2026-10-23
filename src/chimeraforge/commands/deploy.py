"""CLI for config-only deployment export from a validated saved plan."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console


def _replica_groups(values: list[str] | None) -> list[list[str]] | None:
    from chimeraforge.deploy import (
        DeploymentError,
        MAX_EXPORT_GPUS_PER_REPLICA,
        MAX_GPU_IDENTIFIER_CHARS,
    )
    from chimeraforge.planner.constants import MAX_REPLICAS

    if values is None:
        return None
    max_chars = MAX_EXPORT_GPUS_PER_REPLICA * (MAX_GPU_IDENTIFIER_CHARS + 1) - 1
    if type(values) is not list or not 1 <= len(values) <= MAX_REPLICAS:
        raise DeploymentError(
            f"replica device group count must be bounded between 1 and {MAX_REPLICAS}"
        )
    if any(type(value) is not str or not 1 <= len(value) <= max_chars for value in values):
        raise DeploymentError(
            f"each replica device group must be bounded to {max_chars} characters"
        )
    return [value.split(",") for value in values]


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
    gpu_device: list[str] | None = typer.Option(
        None,
        "--gpu-device",
        help="Ordered GPU ordinal or full UUID; repeat TP x PP times (Compose/systemd).",
    ),
    host_port: int | None = typer.Option(
        None,
        "--host-port",
        help="Compose loopback host port (1-65535); native container port stays fixed.",
    ),
    replica_devices: list[str] | None = typer.Option(
        None,
        "--replica-devices",
        help="Comma-separated ordered GPU IDs per replica; repeat in replica order.",
    ),
    replica_port: list[int] | None = typer.Option(
        None,
        "--replica-port",
        help="Explicit loopback host port per replica; repeat in replica order (Compose only).",
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
            output_path=out,
            gpu_devices=gpu_device,
            host_port=host_port,
            replica_gpu_devices=_replica_groups(replica_devices),
            replica_host_ports=replica_port,
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
