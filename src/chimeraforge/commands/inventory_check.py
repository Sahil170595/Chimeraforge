"""CLI for queried inventory mapping and saved batch-one memory arithmetic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer


def inventory_check(
    plan: Path = typer.Option(..., "--plan", help="Original saved-plan JSON."),
    candidate_index: int = typer.Option(0, "--candidate-index"),
    gpu_device: list[str] | None = typer.Option(
        None, "--gpu-device", help="Ordered selector for one replica; repeat."
    ),
    replica_devices: list[str] | None = typer.Option(
        None,
        "--replica-devices",
        help="Ordered comma-separated selectors per original replica; repeat.",
    ),
    timeout: float = typer.Option(
        10.0, "--timeout", help="Native observation seconds, at most 60."
    ),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    """Compare reported inventory with saved B1 memory; no deployment-readiness result."""
    from chimeraforge import api
    from chimeraforge.commands.deploy import _replica_groups
    from chimeraforge.deploy import DeploymentError

    try:
        report = asyncio.run(
            api.check_inventory(
                plan,
                candidate_index=candidate_index,
                gpu_devices=gpu_device,
                replica_gpu_devices=_replica_groups(replica_devices),
                timeout=timeout,
            )
        )
    except (api.InventoryCheckError, DeploymentError) as exc:
        typer.echo(
            json.dumps(
                {
                    "outcome": "invalid",
                    "exit_code": 1,
                    "error": "Invalid saved inventory source or selector declarations.",
                }
            )
            if output_json
            else "Invalid saved inventory source or selector declarations."
        )
        raise typer.Exit(1) from exc
    if output_json:
        typer.echo(json.dumps(report.to_dict(), allow_nan=False))
    else:
        typer.echo(f"Inventory arithmetic {report.outcome}; deployment readiness is unassessed.")
        typer.echo(
            f"Saved B1 baseline: {report.baseline.lower_gib}..{report.baseline.upper_gib} "
            "GiB per entry."
        )
        for slot in report.slots:
            typer.echo(
                f"Replica {slot.replica_index} device {slot.device_index}: "
                f"{slot.selector} {slot.selector_state}; free {slot.free_comparison}; "
                f"{','.join(slot.reasons)}"
            )
        typer.echo("Unassessed: " + ", ".join(report.unassessed))
    raise typer.Exit(report.exit_code)
